# GovSearch with Scrapyd

## Quick Start

### 1. Start all services

```bash
docker compose up --build
```

This will:

- Start OpenSearch and wait for it to be healthy
- Start OpenSearch Dashboards (optional UI)
- Start Scrapyd daemon (ready to accept spider jobs)

### 2. Deploy the spider to Scrapyd

After the services are running, deploy your spider using `scrapyd-deploy`:

```bash
# Deploy from your local machine (recommended)
poetry run scrapyd-deploy scrapyd

# Or deploy from within the container
docker compose exec scrapyd bash -c "cd /app && scrapyd-deploy scrapyd"
```

**Note:** The project is already mounted in the container, so you can also skip deployment and directly schedule spiders (see egg-less deployment below).

### 3. Schedule a spider run

Trigger the spider to crawl your seed URLs:

```bash
curl http://localhost:6800/schedule.json -d project=govsearch -d spider=gov
```

This will return a job ID like: `{"status": "ok", "jobid": "abc123..."}`

### 4. Monitor the spider

Check job status:

```bash
# List all jobs (pending, running, finished)
curl http://localhost:6800/listjobs.json?project=govsearch

# Check daemon status
curl http://localhost:6800/daemonstatus.json
```

View logs in real-time:

```bash
docker compose logs -f scrapyd
```

### 5. Check crawled data

Monitor the data being indexed in OpenSearch:

```bash
# Check OpenSearch is running
curl http://localhost:9200

# Watch the index get populated
curl http://localhost:9200/govsites/_count

# See a sample document
curl http://localhost:9200/govsites/_search?size=1&pretty
```

### 6. View in OpenSearch Dashboards

Open http://localhost:5601 in your browser to explore the data visually.

---

## Scrapyd API Reference

### Schedule a spider run

```bash
curl http://localhost:6800/schedule.json -d project=govsearch -d spider=gov
```

### Cancel a running job

```bash
curl http://localhost:6800/cancel.json -d project=govsearch -d job=<jobid>
```

### List all projects

```bash
curl http://localhost:6800/listprojects.json
```

### List spiders in a project

```bash
curl http://localhost:6800/listspiders.json?project=govsearch
```

### List jobs

```bash
curl http://localhost:6800/listjobs.json?project=govsearch
```

### Access Scrapyd Web UI

Open http://localhost:6800 in your browser to see the Scrapyd web interface.

---

## Troubleshooting

### Egg-less Deployment (Alternative Method)

If the egg deployment isn't working, you can manually copy the project:

```bash
# The project files are already in /app in the container
# Just verify Scrapyd can see them
docker compose exec scrapyd ls -la /app
docker compose exec scrapyd curl http://localhost:6800/listspiders.json?project=govsearch
```

If this works, you can schedule spiders without deploying an egg, since the code is already mounted in the container.

### View Scrapyd logs

```bash
docker compose logs -f scrapyd
```

### View job-specific logs

Job logs are stored in `/var/lib/scrapyd/logs/govsearch/gov/`:

```bash
docker compose exec scrapyd ls -la /var/lib/scrapyd/logs/govsearch/gov/
docker compose exec scrapyd cat /var/lib/scrapyd/logs/govsearch/gov/<jobid>.log
```

### Restart Scrapyd

```bash
docker compose restart scrapyd
```

### Stop everything

```bash
docker compose down
```

### Clean up data and start fresh

```bash
docker compose down -v
```

---

## Advanced Usage

### Run spider with custom settings

```bash
curl http://localhost:6800/schedule.json \
  -d project=govsearch \
  -d spider=gov \
  -d setting=CLOSESPIDER_PAGECOUNT=10
```

### Schedule periodic crawls

You can use a cron job or scheduler to periodically trigger spider runs:

```bash
# Example: Add to crontab to run daily at 2 AM
0 2 * * * curl http://localhost:6800/schedule.json -d project=govsearch -d spider=gov
```

### Monitor with scripts

Create a monitoring script to check job status:

```bash
#!/bin/bash
JOBID=$(curl -s http://localhost:6800/schedule.json -d project=govsearch -d spider=gov | jq -r .jobid)
echo "Started job: $JOBID"

while true; do
  STATUS=$(curl -s http://localhost:6800/listjobs.json?project=govsearch | jq -r ".running[] | select(.id==\"$JOBID\")")
  if [ -z "$STATUS" ]; then
    echo "Job finished!"
    break
  fi
  echo "Job still running..."
  sleep 10
done
```
