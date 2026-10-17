package account

import "testing"

func TestWindowTakesNewestWork(t *testing.T) {
	shares := []Share{
		{"a", 10},
		{"b", 10},
		{"c", 10},
		{"a", 10},
	}
	got := Window(shares, 25)
	if len(got) != 3 || got[0].Address != "b" || got[2].Address != "a" {
		t.Fatalf("window = %+v", got)
	}
	if len(Window(shares, 1000)) != 4 {
		t.Fatal("short history was truncated")
	}
	if Window(nil, 10) != nil {
		t.Fatal("empty history returned shares")
	}
}

func TestFeeIsOnePercentAndBooksBalance(t *testing.T) {
	shares := []Share{{"a", 1}, {"b", 1}, {"c", 1}}
	credits, err := Split(10_000, 1, "fee", shares)
	if err != nil {
		t.Fatal(err)
	}
	var fee, miners, sum int64
	for _, c := range credits {
		sum += c.Amount
		if c.Kind == "fee" {
			fee += c.Amount
			if c.Address != "fee" {
				t.Fatal("fee went to the wrong address")
			}
		} else {
			miners += c.Amount
			if c.Amount != 3300 {
				t.Fatalf("miner credit %d", c.Amount)
			}
		}
	}
	if fee != 100 || miners != 9900 || sum != 10_000 {
		t.Fatalf("fee %d miners %d sum %d", fee, miners, sum)
	}
}

func TestFeeDustDoesNotOverpayMiners(t *testing.T) {
	// 101 satoshis, 1% fee floors to 1. Two equal miners split 100 exactly.
	credits, err := Split(101, 1, "fee", []Share{{"a", 1}, {"b", 1}})
	if err != nil {
		t.Fatal(err)
	}
	var sum int64
	for _, c := range credits {
		sum += c.Amount
		if c.Kind == "miner" && c.Amount != 50 {
			t.Fatalf("miner %s got %d", c.Address, c.Amount)
		}
	}
	if sum != 101 {
		t.Fatalf("sum %d", sum)
	}

	// A reward too small for a 1% fee still balances, and miners never
	// receive more than the reward minus the floored fee.
	credits, err = Split(5, 1, "fee", []Share{{"a", 1}, {"b", 1}})
	if err != nil {
		t.Fatal(err)
	}
	sum = 0
	var minerSum int64
	for _, c := range credits {
		sum += c.Amount
		if c.Kind == "miner" {
			minerSum += c.Amount
		}
	}
	if sum != 5 || minerSum > 5 {
		t.Fatalf("sum %d minerSum %d", sum, minerSum)
	}
}

func TestNoSharesPaysFeeAddress(t *testing.T) {
	credits, err := Split(500, 1, "fee", nil)
	if err != nil {
		t.Fatal(err)
	}
	if len(credits) != 1 || credits[0].Address != "fee" || credits[0].Amount != 500 || credits[0].Kind != "fee" {
		t.Fatalf("%+v", credits)
	}
}

func TestSplitRejectsBadInput(t *testing.T) {
	if _, err := Split(-1, 1, "fee", nil); err == nil {
		t.Fatal("negative reward")
	}
	if _, err := Split(10, 101, "fee", nil); err == nil {
		t.Fatal("percent over 100")
	}
	if _, err := Split(10, 1, "", nil); err == nil {
		t.Fatal("empty fee address")
	}
}
