How to start the server:

`uvicorn main:app --port 7712 --reload`

Endpoints to check:

	http://localhost:7712/api/transactions


Filtered endpoints:

Transactions:

	http://localhost:7712/api/transactions?account=credit
	http://localhost:7712/api/transactions?account=checking

Snapshots:

	http://localhost:7712/api/snapshots
	http://localhost:7712/api/snapshots?account=credit