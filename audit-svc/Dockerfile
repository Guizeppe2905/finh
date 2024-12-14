FROM python:3.11.6-slim-bookworm
RUN python -m pip install \
        --no-color \
        --no-cache-dir \
        --disable-pip-version-check \
        --no-python-version-warning \
        --break-system-packages \
        --progress-bar off \
        poetry setuptools wheel

WORKDIR /opt/audit-svc
COPY ./audit-svc/ ./

RUN mkdir -p dist

RUN poetry export \
        --without-hashes \
        --format constraints.txt \
        --output dist/constraints.txt

RUN poetry run \
        python -m pip wheel \
        --isolated \
        --requirement dist/constraints.txt \
        --wheel-dir dist/vendor

RUN poetry build --format wheel

RUN echo "$(find "dist" "dist/vendor" -maxdepth 1 -iname '*.whl' -exec realpath {} \; -print0 | xargs --null)" > /packages
#RUN export PKGS=$(cat /packages)

RUN python -m pip install \
	--isolated \
	--no-index \
	--no-color \
	--no-cache-dir \
	--disable-pip-version-check \
	--no-python-version-warning \
	--no-warn-script-location \
	--no-deps --progress-bar off \
	$(cat /packages)

CMD ["server"]
