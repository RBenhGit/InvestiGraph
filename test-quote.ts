import yahooFinance from 'yahoo-finance2';
yahooFinance.quote(['AAPL', 'MSFT']).then(r => console.log(r.map(x=>x.symbol + ':' + x.regularMarketPrice)));
