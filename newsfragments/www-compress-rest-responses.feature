Buildbot now compress REST API responses with the appropriate 'accept-encoding' is set.
Available encodings are: gzip, brotli (requires the buildbot[brotli] extra), and zstd (requires the buildbot[zstd] extra)
