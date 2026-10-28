FROM python:3.12-slim
# wget 3.2 has no wheel. Its small distutils setup was inspected (no Git or imports of
# the installed module). Pin the exact source archive; all other packages use wheels.
RUN python -m pip install --no-cache-dir \
    'https://files.pythonhosted.org/packages/47/6a/62e288da7bcda82b935ff0c6cfe542970f04e29c756b0e147251b2fb251f/wget-3.2.zip#sha256=35e630eca2aa50ce998b9b1a127bb26b30dfee573702782aa982f875e3f16061'
RUN python -m pip install --no-cache-dir --only-binary=:all: \
    beautifulsoup4 datasets docker ghapi python-dotenv requests unidiff tqdm pytest cldk==1.0.6
ENV PYTHONPATH=/opt/tdd
ENV PYTHONUNBUFFERED=1
WORKDIR /bench
