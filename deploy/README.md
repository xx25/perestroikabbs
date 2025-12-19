# Docker Deployment Guide

## Quick Start

1. Clone the repository on your target VM:
```bash
git clone <your-repo-url>
cd perestroikabbs
```

2. Configure the BBS:
```bash
cp config.docker.toml config.toml
# Edit config.toml with your specific settings if needed
```

3. Start the services:
```bash
docker-compose up -d
```

4. Initialize the database (first run only):
```bash
docker-compose exec bbs python -m alembic upgrade head
```

5. Connect to the BBS:
```bash
telnet <your-vm-ip> 2323
```

## Configuration

### Environment Variables
You can override database settings using environment variables in `docker-compose.yml`:
- `BBS_DB_HOST`: MySQL host
- `BBS_DB_USER`: Database user
- `BBS_DB_PASSWORD`: Database password
- `BBS_DB_NAME`: Database name

### Volumes
The following directories are persisted:
- MySQL data: `mysql_data` volume
- BBS files: `bbs_files` volume
- User uploads: `bbs_uploads` volume
- Logs: `bbs_logs` volume

### Ports
- BBS Telnet: 2323
- MySQL: 3306 (only exposed locally)

## Management Commands

### View logs
```bash
docker-compose logs -f bbs
```

### Restart BBS
```bash
docker-compose restart bbs
```

### Stop all services
```bash
docker-compose down
```

### Stop and remove all data
```bash
docker-compose down -v
```

### Access BBS shell
```bash
docker-compose exec bbs bash
```

### Backup database
```bash
docker-compose exec mysql mysqldump -u bbs_user -pbbspassword perestroika_bbs > backup.sql
```

### Restore database
```bash
docker-compose exec -T mysql mysql -u bbs_user -pbbspassword perestroika_bbs < backup.sql
```

## Production Deployment

For production, consider:

1. Use secrets management for passwords
2. Set up SSL/TLS termination if needed
3. Configure firewall rules
4. Set up log rotation
5. Configure backups
6. Use a reverse proxy for additional features

### Using Docker Secrets (Swarm mode)
```yaml
services:
  mysql:
    environment:
      MYSQL_ROOT_PASSWORD_FILE: /run/secrets/mysql_root_password
    secrets:
      - mysql_root_password

secrets:
  mysql_root_password:
    external: true
```

### With Traefik reverse proxy
```yaml
services:
  bbs:
    labels:
      - "traefik.enable=true"
      - "traefik.tcp.routers.bbs.rule=HostSNI(`*`)"
      - "traefik.tcp.routers.bbs.entrypoints=telnet"
      - "traefik.tcp.routers.bbs.service=bbs"
      - "traefik.tcp.services.bbs.loadbalancer.server.port=2323"
```

## Troubleshooting

### BBS won't start
Check logs: `docker-compose logs bbs`

### Database connection issues
Ensure MySQL is healthy: `docker-compose ps`

### Permission issues
Check file ownership inside container: `docker-compose exec bbs ls -la /var/lib/bbs`