variable "vpc_id" {}
variable "public_subnet_ids" { type = list(string) }
variable "ecs_target_port" { default = 8000 }

resource "aws_security_group" "alb" {
  name        = "diplomacy-alb-sg"
  description = "Allow HTTP inbound to ALB"
  vpc_id      = var.vpc_id
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_lb" "main" {
  name               = "diplomacy-alb"
  load_balancer_type = "application"
  subnets            = var.public_subnet_ids
  security_groups    = [aws_security_group.alb.id]
  tags = { Name = "diplomacy-alb" }
}

resource "aws_lb_target_group" "ecs" {
  name     = "diplomacy-ecs-tg"
  port     = var.ecs_target_port
  protocol = "HTTP"
  vpc_id   = var.vpc_id
  target_type = "ip"
  health_check {
    path                = "/"
    protocol            = "HTTP"
    matcher             = "200-399"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 2
  }
  tags = { Name = "diplomacy-ecs-tg" }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.ecs.arn
  }
}

# Stub for HTTPS listener (add ACM cert and listener if needed) 