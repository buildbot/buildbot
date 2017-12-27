Any headers passed to an HTTP method of `HTTPCLientService` now override any default header by the same passed at service instantiation time.
When accessing the headers, no matter what backend is used, we now always get back an instance of `twisted.web.http_headers.Headers`
