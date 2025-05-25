# Fleet

## Installation
```shell
cp .env.blank .env && chmod 600 .env
# edit .env and add the required information
pip install -r requirements.txt
docker compose up -d
# when all containers become healthy (in "docker compose ps"):
bin/deploy.sh
```
