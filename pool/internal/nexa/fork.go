package nexa

// TailstormActivation is the Hard Fork 2 mainnet time from nexad
// (consensus.fork2Time): 2026-11-01 01:11:11 UTC.
//
// Before this instant, getminingcandidate's previousBlockHash is 64 zero
// bytes and NexaPow does not mix in a parent. At and after it, nexad puts
// the real parent summary hash in the candidate and CheckProofOfWork signs
// SHA256(SHA256(miningHash || parent)).
const TailstormActivation int64 = 1793495471
