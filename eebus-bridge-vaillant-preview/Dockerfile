# Candidate binary from our fork, pinned by immutable digest and verified
# against the fork's keyless GitHub Actions signer. AMD64 ONLY.
ARG BUILD_FROM=ghcr.io/home-assistant/base:latest

FROM ghcr.io/sigstore/cosign/cosign:v3.1.4@sha256:0f06154836d2de34f887a5c273506d52ca43edaa1d9e53e6510fa78a48f69c2d AS cosign
FROM ghcr.io/regclient/regctl:v0.11.7@sha256:45b57933c2b67bb1e280b4baaa220ef1ab212c81268ab19589fa1e83719c7c82 AS regctl

# hadolint ignore=DL3006
FROM ${BUILD_FROM} AS verified-bridge
COPY --from=cosign /ko-app/cosign /usr/local/bin/cosign
COPY --from=regctl /regctl /usr/local/bin/regctl
COPY fetch-verified-preview.sh /usr/local/bin/fetch-verified-preview
RUN chmod 0755 /usr/local/bin/fetch-verified-preview \
 && /usr/local/bin/fetch-verified-preview \
      "ghcr.io/meneomic/eebus-bridge@sha256:4dfdb01974d7a304beac4b1f739c0953a247646c50abb88661f7b75df78cb938" /verified/eebus-bridge

# Final image contains neither verifier tool nor download credentials.
# hadolint ignore=DL3006
FROM ${BUILD_FROM}
COPY --from=verified-bridge /verified/eebus-bridge /usr/local/bin/eebus-bridge
COPY run.sh /run.sh
COPY import-eebus-identity.sh /usr/local/bin/import-eebus-identity
RUN chmod 0755 /run.sh /usr/local/bin/import-eebus-identity
CMD ["/run.sh"]
