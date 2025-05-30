#

## Build and Push Docker image

```bash
docker build -t docuflow-backend:0.1 .
docker tag docuflow-backend:0.1 819498957810.dkr.ecr.ap-northeast-1.amazonaws.com/nycu/docuflow:0.1
docker push 819498957810.dkr.ecr.ap-northeast-1.amazonaws.com/nycu/docuflow:0.1
```
