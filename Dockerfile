FROM alpine:3.23

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
ARG DUT_CONTROL_REF=9f0b738e80d8c504441d5e04643c606e3a0f6c8e
RUN pip install --no-cache-dir \
      "dut-control @ git+https://github.com/psaavedra/dut-control.git@${DUT_CONTROL_REF}"

ENV PYTHONUNBUFFERED=1
# Importing a suite must not scatter root-owned .pyc through the checkout.
ENV PYTHONDONTWRITEBYTECODE=1

# Fail the build rather than a run at the end of a lab reservation.
RUN python3 -c "import lab_action; print(lab_action.__version__)" \
 && pytest --version \
 && dut-control-client --help > /dev/null \
 && git --version > /dev/null \
 && sshpass -V > /dev/null

ENTRYPOINT ["lab-moonforge-action"]
