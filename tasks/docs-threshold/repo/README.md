# Retry policy

Requests are retried automatically when the upstream returns a 5xx response.

The current limit is 5 retries, after which the request fails.

Retries use exponential backoff starting at 200ms.
