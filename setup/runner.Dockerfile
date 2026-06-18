FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# ── 1. SYSTEM DEPENDENCIES ──────────────────────────────────────────────────
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl git jq sudo ca-certificates \
        python3.10 python3-pip \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1 \
    && update-alternatives --install /usr/bin/python  python   /usr/bin/python3.10 1 \
    && rm -rf /var/lib/apt/lists/*

# ── 2. RUNNER USER CONFIGURATION ────────────────────────────────────────────
RUN useradd -m -s /bin/bash runner \
    && echo 'runner ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers

# ── 3. GITHUB RUNNER CORE ENGINE ────────────────────────────────────────────
ARG RUNNER_VERSION=2.334.0
RUN curl -fsSL -o /tmp/runner.tar.gz \
        "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz" \
    && tar -xzf /tmp/runner.tar.gz -C /home/runner \
    && rm /tmp/runner.tar.gz \
    && /home/runner/bin/installdependencies.sh \
    && chown -R runner:runner /home/runner

# ── 4. EMBEDDED RUNTIME ENTRYPOINT ──────────────────────────────────────────
# Using quoted 'EOF' prevents variable expansion during build
COPY <<'EOF' /entrypoint.sh
#!/bin/bash
set -euo pipefail

RUNNER_NAME="${RUNNER_NAME_PREFIX:-bet-runner}-$(cat /proc/sys/kernel/random/uuid | tr -d '-' | cut -c1-8)"

echo "==> Fetching registration token for ${GITHUB_OWNER}/${GITHUB_REPO}..."
REG_TOKEN=$(curl -sX POST \
    -H "Authorization: token ${ACCESS_TOKEN}" \
    -H "Accept: application/vnd.github.v3+json" \
    "https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/actions/runners/registration-token" \
    | jq -r '.token')

if [ -z "$REG_TOKEN" ] || [ "$REG_TOKEN" = "null" ]; then
    echo "ERROR: Failed to get registration token."
    exit 1
fi

# ── Delete offline ghost runners with the same name prefix ───────────────────
echo "==> Checking for offline ghost runners matching '${RUNNER_NAME_PREFIX:-bet-runner}'..."
RUNNERS=$(curl -s \
    -H "Authorization: token ${ACCESS_TOKEN}" \
    -H "Accept: application/vnd.github.v3+json" \
    "https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/actions/runners?per_page=100")

echo "$RUNNERS" | jq -r \
    --arg prefix "${RUNNER_NAME_PREFIX:-bet-runner}" \
    '.runners[] | select(.name | startswith($prefix)) | select(.status == "offline") | .id' \
| while read -r RUNNER_ID; do
    echo "==> Deleting offline ghost runner ID ${RUNNER_ID}..."
    curl -sX DELETE \
        -H "Authorization: token ${ACCESS_TOKEN}" \
        -H "Accept: application/vnd.github.v3+json" \
        "https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/actions/runners/${RUNNER_ID}"
done

# ── Remove stale local config ─────────────────────────────────────────────────
if [ -f ".runner" ]; then
    echo "==> Removing stale local runner config..."
    REMOVE_TOKEN=$(curl -sX POST \
        -H "Authorization: token ${ACCESS_TOKEN}" \
        -H "Accept: application/vnd.github.v3+json" \
        "https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/actions/runners/remove-token" \
        | jq -r '.token')
    ./config.sh remove --unattended --token "${REMOVE_TOKEN}" 2>/dev/null \
        || rm -f .runner .credentials .credentials_rsaparams
fi

echo "==> Registering runner as '${RUNNER_NAME}'..."
./config.sh \
    --url "https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}" \
    --token "${REG_TOKEN}" \
    --name "${RUNNER_NAME}" \
    --labels "${LABELS:-self-hosted,linux,bet-runner}" \
    --work "_work" \
    --unattended \
    --replace

cleanup() {
    echo "==> Deregistering runner '${RUNNER_NAME}'..."
    ./config.sh remove --unattended --token "${REG_TOKEN}" || true
}
trap cleanup EXIT INT TERM

echo "==> Runner '${RUNNER_NAME}' ready."
./run.sh
EOF

# Ensure script is executable and normalized for Linux
RUN chmod +x /entrypoint.sh && sed -i 's/\r$//' /entrypoint.sh

# ── 5. PYTHON APPLICATION LAYER ─────────────────────────────────────────────
USER runner
WORKDIR /home/runner

# Force local binaries to be discoverable
ENV PATH="/home/runner/.local/bin:${PATH}"

# Upgrade build tools to prevent 'UNKNOWN' package naming bug
RUN pip3 install --no-cache-dir --user --upgrade pip setuptools wheel

# Install requirements
COPY --chown=runner:runner setup/requirements-scrape.txt /tmp/requirements-scrape.txt
RUN pip3 install --no-cache-dir --user -r /tmp/requirements-scrape.txt

# Install browsers natively
RUN scrapling install

# Explicitly invoke bash to execute the script
ENTRYPOINT ["/bin/bash", "/entrypoint.sh"]
