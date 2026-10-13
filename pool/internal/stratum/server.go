// Package stratum speaks the Nexa echelon dialect used by lolMiner, BzMiner,
// Rigel and SRBMiner. The message shapes follow the echelon specification
// and the Nexa handlers in magicpool-co/pool: subscribe, authorize,
// set_difficulty, notify, and submit. WildRig's five-parameter submit is
// accepted as well.
package stratum

import (
	"bufio"
	"crypto/rand"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"net"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"github.com/jQrgen/nordic-crypto/pool/internal/nexa"
)

const (
	errOther         = 20
	errStale         = 21
	errDuplicate     = 22
	errLowDiff       = 23
	errUnauthorized  = 24
	errNotSubscribed = 25
)

// Job is one mining candidate pushed to miners.
type Job struct {
	ID            string
	Commitment    string // 64 hex chars, display order
	NBits         string // 8 hex chars
	PrevHash      string // 64 hex chars, display order; zeros before Tailstorm
	Time          uint64
	Height        int64
	CandidateID   int64
	Clean         bool
	NetworkTarget []byte // unused by the wire format; the pool checks shares itself
}

// Share is a solution a miner submitted.
type Share struct {
	Address          string
	Worker           string
	JobID            string
	Nonce            []byte
	NTime            uint64
	DifficultyMicros uint64
	Agent            string
}

// Verdict is what the pool decided about a share.
type Verdict struct {
	Accept  bool
	Code    int
	Message string
}

// Hooks are the pool's decisions. The stratum server does not touch the
// database or the node itself.
type Hooks struct {
	Authorize func(address, worker string) error
	Submit    func(Share) Verdict
}

// Server is a newline-delimited JSON stratum listener.
type Server struct {
	Hooks     Hooks
	StartDiff uint64
	MinDiff   uint64
	MaxDiff   uint64
	VarDiff   bool

	// MaxPerIP caps sessions from one remote address. Zero uses the default.
	MaxPerIP int
	// ReadTimeout is how long a session may go without completing a line.
	// Zero uses the default. A slow drip cannot hold a slot for longer.
	ReadTimeout time.Duration
	// SubmitRate is the sustained mining.submit rate per session, per second.
	SubmitRate float64
	// SubmitBurst is how many submits may arrive at once before the limit.
	SubmitBurst float64
	// BanAfter is how many bad shares or rate-limit hits ban the remote IP.
	BanAfter int
	// SubmitGrace is how long a new session may exceed SubmitRate without
	// being banned. Variable difficulty retargets faster during the same
	// window so an honest fast miner is not banned before the difficulty
	// can rise. Zero uses the default.
	SubmitGrace time.Duration

	ln       net.Listener
	mu       sync.Mutex
	conns    map[*session]struct{}
	extras   map[string]struct{}
	perIP    map[string]int
	bans     map[string]time.Time
	job      Job
	hasJob   bool
	closed   atomic.Bool
	writeFor time.Duration
}

// Listen starts serving on addr, for example "0.0.0.0:3333".
func (s *Server) Listen(addr string) error {
	if s.StartDiff == 0 {
		s.StartDiff = 200_000
	}
	if s.MinDiff == 0 {
		s.MinDiff = 50_000
	}
	if s.MaxDiff == 0 {
		s.MaxDiff = 4096 * nexa.Micros
	}
	if s.MaxPerIP <= 0 {
		s.MaxPerIP = 16
	}
	if s.ReadTimeout <= 0 {
		s.ReadTimeout = 60 * time.Second
	}
	if s.SubmitRate <= 0 {
		// 128/s at the 0.2 start difficulty is about 110 GH/s. The grace
		// window below is what lets a faster miner ramp before a ban.
		s.SubmitRate = 128
	}
	if s.SubmitBurst <= 0 {
		s.SubmitBurst = 256
	}
	if s.BanAfter <= 0 {
		s.BanAfter = 20
	}
	if s.SubmitGrace <= 0 {
		s.SubmitGrace = 3 * time.Minute
	}
	if s.writeFor <= 0 {
		s.writeFor = 5 * time.Second
	}
	ln, err := net.Listen("tcp", addr)
	if err != nil {
		return err
	}
	s.ln = ln
	s.mu.Lock()
	s.conns = map[*session]struct{}{}
	s.extras = map[string]struct{}{}
	s.perIP = map[string]int{}
	s.bans = map[string]time.Time{}
	s.mu.Unlock()
	go s.accept()
	return nil
}

// Addr is the bound address, useful when tests pass port 0.
func (s *Server) Addr() string {
	if s.ln == nil {
		return ""
	}
	return s.ln.Addr().String()
}

// Close stops the listener and the open sessions.
func (s *Server) Close() error {
	s.closed.Store(true)
	var err error
	if s.ln != nil {
		err = s.ln.Close()
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	for c := range s.conns {
		c.conn.Close()
	}
	return err
}

// SetJob broadcasts a candidate. clean in the job tells miners whether to
// drop older work.
func (s *Server) SetJob(job Job) {
	s.mu.Lock()
	s.job = job
	s.hasJob = true
	conns := make([]*session, 0, len(s.conns))
	for c := range s.conns {
		conns = append(conns, c)
	}
	s.mu.Unlock()
	for _, c := range conns {
		if c.authorized.Load() {
			c.notify(job)
		}
	}
}

// NotifyParams is the mining.notify parameter list. Before Tailstorm it is
// the echelon five-tuple. When the job carries a real previousBlockHash,
// which is how the node says Tailstorm is on, a sixth value is appended in
// the same display order nexad's getminingcandidate uses (uint256::GetHex).
// Miners reverse that hex before mixing it into the Tailstorm digest,
// which is what nexa-miner does. The switch is the parent, not the clock.
func NotifyParams(job Job) []any {
	ts := make([]byte, 8)
	binary.BigEndian.PutUint64(ts, job.Time)
	params := []any{job.ID, job.Commitment, job.NBits, hex.EncodeToString(ts), job.Clean}
	if nexa.TailstormParent(job.PrevHash) {
		params = append(params, strings.ToLower(job.PrevHash))
	}
	return params
}

func (s *Server) currentJob() (Job, bool) {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.job, s.hasJob
}

func (s *Server) accept() {
	for {
		conn, err := s.ln.Accept()
		if err != nil {
			if s.closed.Load() {
				return
			}
			continue
		}
		host := remoteHost(conn)
		s.mu.Lock()
		if s.bannedLocked(host) || s.perIP[host] >= s.MaxPerIP || len(s.conns) >= 4096 {
			s.mu.Unlock()
			conn.Close()
			continue
		}
		extra, err := s.uniqueExtraLocked()
		if err != nil {
			s.mu.Unlock()
			conn.Close()
			continue
		}
		sess := newSession(s, conn, host, extra)
		s.conns[sess] = struct{}{}
		s.extras[extra] = struct{}{}
		s.perIP[host]++
		s.mu.Unlock()
		go func() {
			sess.run()
			s.mu.Lock()
			delete(s.conns, sess)
			delete(s.extras, sess.extra)
			s.perIP[host]--
			if s.perIP[host] <= 0 {
				delete(s.perIP, host)
			}
			s.mu.Unlock()
		}()
	}
}

func remoteHost(conn net.Conn) string {
	host, _, err := net.SplitHostPort(conn.RemoteAddr().String())
	if err != nil {
		return conn.RemoteAddr().String()
	}
	if ip := net.ParseIP(host); ip != nil {
		return ip.String()
	}
	return host
}

func (s *Server) uniqueExtraLocked() (string, error) {
	for i := 0; i < 8; i++ {
		buf := make([]byte, 8)
		if _, err := rand.Read(buf); err != nil {
			return "", err
		}
		extra := hex.EncodeToString(buf)
		if _, ok := s.extras[extra]; !ok {
			return extra, nil
		}
	}
	return "", errors.New("stratum: extranonce collision")
}

func (s *Server) bannedLocked(host string) bool {
	until, ok := s.bans[host]
	if !ok {
		return false
	}
	if time.Now().After(until) {
		delete(s.bans, host)
		return false
	}
	return true
}

func (s *Server) ban(host string, until time.Time) {
	s.mu.Lock()
	s.bans[host] = until
	s.mu.Unlock()
}

type session struct {
	srv        *Server
	conn       net.Conn
	out        chan []byte
	writeMu    sync.Mutex
	closing    bool
	subscribed atomic.Bool
	authorized atomic.Bool
	address    string
	worker     string
	agent      string
	host       string
	extra      string
	diff       atomic.Uint64
	vardiff    *VarDiff
	bad        int
	tokens     float64
	tokenAt    time.Time
	started    time.Time
}

func newSession(srv *Server, conn net.Conn, host, extra string) *session {
	now := time.Now()
	vd := newVarDiff(srv.StartDiff, srv.MinDiff, srv.MaxDiff, now)
	vd.grace = srv.SubmitGrace
	return &session{
		srv:     srv,
		conn:    conn,
		host:    host,
		out:     make(chan []byte, 8),
		extra:   extra,
		vardiff: vd,
		tokens:  srv.SubmitBurst,
		tokenAt: now,
		started: now,
	}
}

func (s *session) run() {
	defer s.conn.Close()
	defer s.stopWriter()
	go s.writer()
	s.diff.Store(s.srv.StartDiff)
	s.conn.SetReadDeadline(time.Now().Add(s.srv.ReadTimeout))
	sc := bufio.NewScanner(s.conn)
	sc.Buffer(make([]byte, 0, 4096), 64*1024)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" {
			continue
		}
		s.conn.SetReadDeadline(time.Now().Add(s.srv.ReadTimeout))
		s.handle(line)
	}
}

func (s *session) writer() {
	for raw := range s.out {
		s.conn.SetWriteDeadline(time.Now().Add(s.srv.writeFor))
		if _, err := s.conn.Write(raw); err != nil {
			s.conn.Close()
			return
		}
	}
}

func (s *session) stopWriter() {
	s.writeMu.Lock()
	defer s.writeMu.Unlock()
	if s.closing {
		return
	}
	s.closing = true
	close(s.out)
}

type request struct {
	ID     json.RawMessage `json:"id"`
	Method string          `json:"method"`
	Params json.RawMessage `json:"params"`
}

func (s *session) handle(line string) {
	var req request
	if err := json.Unmarshal([]byte(line), &req); err != nil {
		s.reply(json.RawMessage("null"), nil, errOther, "bad json")
		return
	}
	if len(req.ID) == 0 {
		req.ID = json.RawMessage("null")
	}
	switch req.Method {
	case "mining.subscribe":
		s.subscribe(req)
	case "mining.authorize":
		s.authorize(req)
	case "mining.submit":
		s.submit(req)
	case "mining.suggest_difficulty":
		s.suggest(req)
	case "mining.extranonce.subscribe":
		s.reply(req.ID, true, 0, "")
	default:
		s.reply(req.ID, nil, errOther, "unknown method")
	}
}

func (s *session) subscribe(req request) {
	params := stringParams(req.Params)
	if len(params) > 0 {
		s.agent = params[0]
	}
	s.subscribed.Store(true)
	sub := s.extra[:8]
	result := []any{
		[]any{
			[]any{"mining.set_difficulty", sub},
			[]any{"mining.notify", sub},
		},
		s.extra,
		8,
	}
	s.reply(req.ID, result, 0, "")
}

func (s *session) authorize(req request) {
	if !s.subscribed.Load() {
		s.reply(req.ID, false, errNotSubscribed, "Not subscribed")
		return
	}
	params := stringParams(req.Params)
	if len(params) < 1 || params[0] == "" {
		s.reply(req.ID, false, errUnauthorized, "Unauthorized worker")
		return
	}
	address, worker := splitUser(params[0])
	if s.srv.Hooks.Authorize != nil {
		if err := s.srv.Hooks.Authorize(address, worker); err != nil {
			s.reply(req.ID, false, errUnauthorized, "Unauthorized worker")
			return
		}
	}
	s.address = address
	s.worker = worker
	s.authorized.Store(true)
	s.reply(req.ID, true, 0, "")
	s.sendDifficulty(s.diff.Load())
	if job, ok := s.srv.currentJob(); ok {
		s.notify(job)
	}
}

func (s *session) submit(req request) {
	if !s.subscribed.Load() {
		s.reply(req.ID, false, errNotSubscribed, "Not subscribed")
		return
	}
	if !s.authorized.Load() {
		s.reply(req.ID, false, errUnauthorized, "Unauthorized worker")
		return
	}
	var params []json.RawMessage
	if err := json.Unmarshal(req.Params, &params); err != nil || (len(params) != 4 && len(params) != 5) {
		s.reply(req.ID, false, errOther, "bad submit")
		return
	}
	var user, jobID, nonceHex, extra2, stamp string
	_ = json.Unmarshal(params[0], &user)
	_ = json.Unmarshal(params[1], &jobID)
	switch len(params) {
	case 4:
		_ = json.Unmarshal(params[2], &nonceHex)
		_ = json.Unmarshal(params[3], &stamp)
	case 5:
		// WildRig sends extranonce2, time, then the miner nonce.
		_ = json.Unmarshal(params[2], &extra2)
		_ = json.Unmarshal(params[3], &stamp)
		_ = json.Unmarshal(params[4], &nonceHex)
		nonceHex = extra2 + nonceHex
	}
	ntime, err := parseNTime(stamp)
	if err != nil {
		s.reply(req.ID, false, errOther, "bad time")
		s.penalise()
		return
	}
	if job, ok := s.srv.currentJob(); ok && job.ID == jobID && job.Time != ntime {
		s.reply(req.ID, false, errOther, "bad time")
		s.penalise()
		return
	}
	now := time.Now()
	if !s.allowSubmit(now) {
		s.reply(req.ID, false, errOther, "rate limit")
		// During the ramp the limit still sheds load, but it does not
		// ban. Variable difficulty is climbing on the shares that land.
		if s.rateLimitBans(now) {
			s.penalise()
		}
		return
	}
	nonce, err := bindNonce(s.extra, nonceHex)
	if err != nil {
		s.reply(req.ID, false, errOther, "bad nonce")
		s.penalise()
		return
	}
	address, worker := s.address, s.worker
	if user != "" {
		uAddr, uWorker := splitUser(user)
		if !strings.EqualFold(uAddr, s.address) {
			s.reply(req.ID, false, errUnauthorized, "Unauthorized worker")
			return
		}
		if uWorker != "" {
			worker = uWorker
		}
	}
	verdict := Verdict{Accept: true}
	if s.srv.Hooks.Submit != nil {
		verdict = s.srv.Hooks.Submit(Share{
			Address: address, Worker: worker, JobID: jobID, Nonce: nonce,
			NTime: ntime, DifficultyMicros: s.diff.Load(), Agent: s.agent,
		})
	}
	if !verdict.Accept {
		code := verdict.Code
		if code == 0 {
			code = errLowDiff
		}
		msg := verdict.Message
		if msg == "" {
			msg = "rejected"
		}
		s.reply(req.ID, false, code, msg)
		if code == errOther || code == errLowDiff {
			s.penalise()
		}
		return
	}
	s.reply(req.ID, true, 0, "")
	if s.srv.VarDiff {
		if next, changed := s.vardiff.Observe(time.Now()); changed {
			s.diff.Store(next)
			s.sendDifficulty(next)
			if job, ok := s.srv.currentJob(); ok {
				job.Clean = false
				s.notify(job)
			}
		}
	}
}

func (s *session) suggest(req request) {
	if !s.authorized.Load() {
		s.reply(req.ID, false, errUnauthorized, "Unauthorized worker")
		return
	}
	var params []float64
	if err := json.Unmarshal(req.Params, &params); err != nil || len(params) < 1 || params[0] <= 0 {
		s.reply(req.ID, false, errOther, "bad difficulty")
		return
	}
	micros := uint64(params[0] * float64(nexa.Micros))
	floor := s.diff.Load()
	if floor < s.srv.MinDiff {
		floor = s.srv.MinDiff
	}
	if micros < floor {
		s.reply(req.ID, false, errOther, "difficulty below floor")
		return
	}
	if micros > s.srv.MaxDiff {
		micros = s.srv.MaxDiff
	}
	s.diff.Store(micros)
	s.vardiff.micros = micros
	s.reply(req.ID, true, 0, "")
	s.sendDifficulty(micros)
}

func (s *session) allowSubmit(now time.Time) bool {
	rate := s.srv.SubmitRate
	burst := s.srv.SubmitBurst
	if rate <= 0 {
		return true
	}
	elapsed := now.Sub(s.tokenAt).Seconds()
	if elapsed > 0 {
		s.tokens += elapsed * rate
		s.tokenAt = now
	}
	if s.tokens > burst {
		s.tokens = burst
	}
	if s.tokens < 1 {
		return false
	}
	s.tokens--
	return true
}

func (s *session) rateLimitBans(now time.Time) bool {
	if s.srv.SubmitGrace <= 0 {
		return true
	}
	return now.Sub(s.started) >= s.srv.SubmitGrace
}

func (s *session) penalise() {
	s.bad++
	if s.srv.BanAfter > 0 && s.bad >= s.srv.BanAfter {
		s.srv.ban(s.host, time.Now().Add(10*time.Minute))
		s.conn.Close()
	}
}

func (s *session) notify(job Job) {
	s.notifyRaw(map[string]any{
		"id": nil, "method": "mining.notify",
		"params": NotifyParams(job),
	})
}

func (s *session) sendDifficulty(micros uint64) {
	diff := float64(micros) / float64(nexa.Micros)
	s.notifyRaw(map[string]any{
		"id": nil, "method": "mining.set_difficulty", "params": []any{diff},
	})
}

func (s *session) reply(id json.RawMessage, result any, code int, msg string) {
	body := map[string]any{"id": json.RawMessage(id), "result": result, "error": nil}
	if code != 0 {
		body["result"] = result
		body["error"] = []any{code, msg, nil}
	}
	s.notifyRaw(body)
}

func (s *session) notifyRaw(v any) {
	raw, err := json.Marshal(v)
	if err != nil {
		return
	}
	raw = append(raw, '\n')
	s.writeMu.Lock()
	defer s.writeMu.Unlock()
	if s.closing {
		return
	}
	select {
	case s.out <- raw:
	default:
		// The client is not reading. Drop it instead of stalling the
		// broadcast for everyone else.
		s.conn.Close()
	}
}

func stringParams(raw json.RawMessage) []string {
	var items []any
	if json.Unmarshal(raw, &items) != nil {
		return nil
	}
	out := make([]string, len(items))
	for i, item := range items {
		if s, ok := item.(string); ok {
			out[i] = s
		}
	}
	return out
}

func splitUser(user string) (address, worker string) {
	user = strings.TrimSpace(user)
	for _, sep := range []string{".", "/"} {
		if i := strings.LastIndex(user, sep); i > 0 && strings.Contains(user[:i], ":") {
			return user[:i], user[i+1:]
		}
	}
	return user, ""
}

func parseNTime(stamp string) (uint64, error) {
	stamp = strings.TrimSpace(strings.ToLower(stamp))
	stamp = strings.TrimPrefix(stamp, "0x")
	if stamp == "" || len(stamp) > 16 {
		return 0, errors.New("bad time")
	}
	if len(stamp)%2 != 0 {
		stamp = "0" + stamp
	}
	raw, err := hex.DecodeString(stamp)
	if err != nil || len(raw) == 0 || len(raw) > 8 {
		return 0, errors.New("bad time")
	}
	var v uint64
	for _, c := range raw {
		v = v<<8 | uint64(c)
	}
	return v, nil
}

func bindNonce(extra, nonceHex string) ([]byte, error) {
	nonceHex = strings.ToLower(strings.TrimPrefix(strings.TrimPrefix(nonceHex, "0x"), "0X"))
	if nonceHex == "" || len(nonceHex)%2 != 0 {
		return nil, errors.New("bad nonce")
	}
	extra = strings.ToLower(extra)
	if !strings.HasPrefix(nonceHex, extra) {
		if len(extra)+len(nonceHex) > 32 {
			return nil, errors.New("nonce missing extranonce")
		}
		nonceHex = extra + nonceHex
	}
	nonce, err := hex.DecodeString(nonceHex)
	if err != nil || len(nonce) == 0 || len(nonce) > 16 {
		return nil, errors.New("bad nonce")
	}
	return nonce, nil
}

// ErrClosed is returned when the listener has stopped.
var ErrClosed = io.EOF
