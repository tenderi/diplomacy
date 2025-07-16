variable "db_name" { default = "diplomacy" }
variable "db_username" { default = "diplomacy" }
variable "db_password" { default = "diplomacy" }
variable "vpc_id" {}
variable "subnet_ids" { type = list(string) }
variable "rds_sg_id" { description = "RDS security group ID" }

resource "aws_db_subnet_group" "main" {
  name       = "diplomacy-db-subnet-group"
  subnet_ids = var.subnet_ids
  tags = { Name = "diplomacy-db-subnet-group" }
}

resource "aws_db_instance" "main" {
  identifier              = "diplomacy-db"
  engine                  = "postgres"
  engine_version          = "15.5"
  instance_class          = "db.t3.micro"
  allocated_storage       = 20
  db_name                    = var.db_name
  username                = var.db_username
  password                = var.db_password
  db_subnet_group_name    = aws_db_subnet_group.main.name
  vpc_security_group_ids  = [var.rds_sg_id]
  skip_final_snapshot     = true
  publicly_accessible     = false
  multi_az                = false
  storage_encrypted       = true
  backup_retention_period = 0
  tags = { Name = "diplomacy-db" }
} 