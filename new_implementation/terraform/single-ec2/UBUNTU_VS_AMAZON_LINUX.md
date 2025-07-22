# Ubuntu vs Amazon Linux 2 for Single EC2 Deployment

## Current Issues with Amazon Linux 2

After implementing the single EC2 deployment, we encountered several issues with Amazon Linux 2:

1. **PostgreSQL Installation Complexity**
   - `amazon-linux-extras` doesn't create postgres user automatically
   - `initdb` binary path varies by version (`/usr/pgsql-*/bin/initdb`)
   - Required custom logic to find and initialize database

2. **Python Package Compatibility**
   - Limited to older package versions (FastAPI 0.103.2 vs 0.115.6)
   - Major version downgrades required (SQLAlchemy 2.0 → 1.4, Pydantic 2.x → 1.x)
   - Potential application code compatibility issues

3. **Development Experience**
   - Fewer online tutorials and Stack Overflow answers
   - AWS-specific package management (`amazon-linux-extras`)
   - More debugging time for basic setup tasks

## Comparison

| Aspect | Amazon Linux 2 | Ubuntu 22.04 LTS |
|--------|----------------|-------------------|
| **PostgreSQL Setup** | Complex (custom initdb path) | Simple (`apt install postgresql`) |
| **Python Packages** | Old versions (compatibility issues) | Latest versions (FastAPI 0.115+) |
| **Base RAM Usage** | ~120MB | ~180MB |
| **Documentation** | Limited, AWS-focused | Extensive community docs |
| **Package Repository** | amazon-linux-extras + yum | apt (massive repository) |
| **Security Updates** | AWS-managed | Canonical-managed |
| **AWS Integration** | Optimized | Standard (works fine) |
| **Cost** | Free Tier eligible | Free Tier eligible |

## Recommendation: Switch to Ubuntu

### Why Ubuntu is Better for Our Use Case:

1. **Simplicity First**: Our goal is the cheapest, simplest deployment
2. **Development Speed**: Less time debugging AWS-specific issues
3. **Modern Packages**: Can use latest FastAPI, SQLAlchemy, Pydantic
4. **Familiar**: Most developers know Ubuntu better
5. **Resource Impact**: 60MB RAM difference is negligible on t3.micro

### Ubuntu Setup Comparison

**Amazon Linux 2 (Current):**
```bash
# 15+ lines of complex PostgreSQL setup
amazon-linux-extras install postgresql14
useradd -r -s /bin/false postgres  # Manual user creation
# Custom initdb path detection logic
sudo -u postgres /usr/pgsql-14/bin/initdb -D /var/lib/pgsql/data

# Downgraded Python packages
fastapi==0.103.2  # Old version
sqlalchemy==1.4.53  # Major version downgrade
```

**Ubuntu (Proposed):**
```bash
# 3 lines of standard PostgreSQL setup
sudo apt install -y postgresql postgresql-contrib
sudo systemctl enable postgresql
sudo -u postgres createdb diplomacy

# Latest Python packages
fastapi==0.115.6  # Latest version
sqlalchemy==2.0.36  # Latest version
```

## Migration Path

If we decide to switch:

1. **Create Ubuntu variant**: `terraform/single-ec2-ubuntu/`
2. **Update AMI**: Use Ubuntu 22.04 LTS instead of Amazon Linux 2
3. **Simplify user_data.sh**: Remove AL2-specific workarounds
4. **Test deployment**: Should be much more reliable
5. **Keep AL2 version**: For comparison and fallback

## Cost Impact: None

Both Amazon Linux 2 and Ubuntu are:
- ✅ Free Tier eligible
- ✅ No licensing costs
- ✅ Same EC2 instance costs
- ✅ Same bandwidth/storage costs

The only difference is slightly higher RAM usage (60MB), which doesn't affect costs on t3.micro.

## Performance Impact: Minimal

On a t3.micro (1GB RAM, 2 vCPU):
- **60MB RAM difference**: 6% of total memory
- **Boot time**: Ubuntu ~30s vs AL2 ~25s
- **Application performance**: Identical for our use case

## Security Considerations

- **Amazon Linux 2**: Fewer packages = smaller attack surface
- **Ubuntu**: More packages but also more frequent security updates
- **Both**: Require same security hardening practices
- **Impact**: Negligible for single-instance deployment

## Conclusion

For our simple, cost-optimized Diplomacy server deployment, **Ubuntu offers significant advantages in simplicity and maintainability** with minimal downsides.

The 60MB RAM overhead is a worthwhile trade-off for:
- ✅ Dramatically simpler setup
- ✅ Latest package versions
- ✅ Better development experience
- ✅ Future-proof application compatibility 