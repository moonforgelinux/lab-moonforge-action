# Robot Framework, as a second tag on top of the default image.
#
# Facts that shape this file:
# - robotframework-doctestlibrary needs PyMuPDF, which has no musl
#   wheel for aarch64. This image is amd64 only.
# - opencv-python-headless has no musl wheel at all. OpenCV comes from
#   apk, with a dist-info alias so pip stops looking for the wheel.
# - Wand, pyzbar, pylibdmtx and pytesseract are bindings. The
#   libraries they bind come from apk too.
#
# Built from the default image, so both carry the same lab_action and
# the same dut-control client. BASE has to come from this same commit:
# the package and the extras list below are the ones it carries.
ARG BASE=lab-moonforge-action:latest
FROM ${BASE}

RUN apk add --no-cache \
      imagemagick \
      libdmtx \
      py3-opencv \
      tesseract-ocr \
      zbar

# The venv was made without them, and cv2 lives outside it.
RUN sed -i 's/^include-system-site-packages = false/include-system-site-packages = true/' \
      /opt/venv/pyvenv.cfg

# pip cannot know apk installed cv2, and the wheel it would go for
# does not exist for musl. A dist-info under the name the doctest
# library asks for settles it.
RUN set -eu; \
    site=$(python3 -c 'import site; print(site.getsitepackages()[0])'); \
    version=$(python3 -c 'import cv2; print(cv2.__version__)'); \
    info="$site/opencv_python_headless-${version}.dist-info"; \
    mkdir -p "$info"; \
    printf 'Metadata-Version: 2.1\nName: opencv-python-headless\nVersion: %s\n' \
      "$version" > "$info/METADATA"; \
    : > "$info/INSTALLER"; \
    : > "$info/RECORD"

WORKDIR /src
RUN pip install --no-cache-dir --prefer-binary ".[robot]"

# Fail the build rather than a run at the end of a lab reservation.
RUN python3 -c "import robot; print(robot.version.VERSION)" \
 && python3 -c "import cv2; print(cv2.__version__)" \
 && python3 -c "import pymupdf" \
 && python3 -c "import DocTest" \
 && command -v robot > /dev/null
