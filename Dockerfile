# Pinned by digest, so rebuilding a release gives the same bits. This
# is the index, not one architecture: both amd64 and arm64 are in it.
FROM alpine:3.24@sha256:f59abe656b692d901e184be3445e084786602108599d2a51d229c0f5a48c71bf

# git for checkouts the suites may do themselves, ssh and sshpass so a
# suite can log in to a device with the empty root password a debug
# Moonforge image leaves.
RUN apk add --no-cache \
      bash \
      ca-certificates \
      git \
      openssh-client \
      sshpass \
      python3 \
      py3-pip

ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
RUN python3 -m venv "$VIRTUAL_ENV"

WORKDIR /src
COPY pyproject.toml README.md ./
COPY lab_action ./lab_action
RUN pip install --no-cache-dir ".[suite]"

# Pinned by commit: the lifecycle depends on what this client can do.
ARG DUT_CONTROL_REF=5fa85a8479ec8467ae50b4824be265064e28f7fa
RUN pip install --no-cache-dir \
      "dut-control @ git+https://github.com/psaavedra/dut-control.git@${DUT_CONTROL_REF}"

ENV PYTHONUNBUFFERED=1
# Importing a suite must not scatter root-owned .pyc through the checkout.
ENV PYTHONDONTWRITEBYTECODE=1

# Fail the build rather than a run at the end of a lab reservation.
RUN python3 -c "import lab_action; print(lab_action.__version__)" \
 && pytest --version \
 && git --version > /dev/null \
 && sshpass -V > /dev/null \
 && for c in reserve lease power flash wait wipe; do \
      dut-control-client "$c" --help > /dev/null \
        || { echo "dut-control-client has no $c"; exit 1; }; \
    done

ENTRYPOINT ["lab-moonforge-action"]
