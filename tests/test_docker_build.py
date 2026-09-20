"""
Unit Tests for Production Containerization, Dockerfile, and Docker Compose Configuration
(tests/test_docker_build.py)
"""

import os
import unittest
import yaml


class TestDockerConfiguration(unittest.TestCase):
    def setUp(self):
        self.repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.dockerfile_path = os.path.join(self.repo_root, "Dockerfile")
        self.dockerignore_path = os.path.join(self.repo_root, ".dockerignore")
        self.compose_path = os.path.join(self.repo_root, "docker-compose.yml")
        self.prom_config_path = os.path.join(self.repo_root, "deploy", "prometheus.yml")

    def test_01_dockerfile_multistage_and_security(self):
        """Verify Dockerfile multi-stage build, non-root user, and security hardening."""
        self.assertTrue(os.path.exists(self.dockerfile_path), "Dockerfile must exist at repository root")
        with open(self.dockerfile_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Multi-stage build
        self.assertIn("AS builder", content, "Dockerfile must use a builder stage")
        self.assertIn("AS runner", content, "Dockerfile must use a runner stage")

        # Non-root user security (CIS Docker Benchmark)
        self.assertIn("useradd", content, "Dockerfile must create an unprivileged user")
        self.assertIn("USER appuser", content, "Dockerfile must switch to non-root appuser")
        self.assertIn("10001", content, "Dockerfile must use explicit non-root UID 10001")

        # Expose and healthcheck
        self.assertIn("EXPOSE 8000", content, "Dockerfile must expose port 8000")
        self.assertIn("HEALTHCHECK", content, "Dockerfile must define a container healthcheck")
        self.assertIn("/api/telemetry/dashboard", content, "Healthcheck must probe telemetry SLA dashboard")
        self.assertIn("uvicorn", content, "Entrypoint must launch uvicorn")

    def test_02_dockerignore_coverage(self):
        """Verify .dockerignore excludes sensitive and temporary artifacts."""
        self.assertTrue(os.path.exists(self.dockerignore_path), ".dockerignore must exist at repository root")
        with open(self.dockerignore_path, "r", encoding="utf-8") as f:
            ignored = [line.strip() for line in f if line.strip() and not line.startswith("#")]

        self.assertIn(".git", ignored)
        self.assertIn(".venv", ignored)
        self.assertIn("__pycache__/", ignored)
        self.assertIn("STOP", ignored)

    def test_03_docker_compose_validity(self):
        """Verify docker-compose.yml valid YAML structure, services, and networking."""
        self.assertTrue(os.path.exists(self.compose_path), "docker-compose.yml must exist at repository root")
        with open(self.compose_path, "r", encoding="utf-8") as f:
            compose = yaml.safe_load(f)

        self.assertIn("services", compose)
        services = compose["services"]

        # 1. tigergraph-agent service
        self.assertIn("tigergraph-agent", services)
        agent_svc = services["tigergraph-agent"]
        self.assertEqual(agent_svc["ports"], ["8000:8000"])
        self.assertIn("healthcheck", agent_svc)
        self.assertEqual(agent_svc["restart"], "unless-stopped")

        # 2. prometheus service
        self.assertIn("prometheus", services)
        prom_svc = services["prometheus"]
        self.assertEqual(prom_svc["ports"], ["9090:9090"])
        self.assertIn("depends_on", prom_svc)
        self.assertIn("tigergraph-agent", prom_svc["depends_on"])

        # 3. Networks
        self.assertIn("networks", compose)
        self.assertIn("fraud-net", compose["networks"])

    def test_04_prometheus_scrape_configuration(self):
        """Verify deploy/prometheus.yml valid YAML and scrape config."""
        self.assertTrue(os.path.exists(self.prom_config_path), "deploy/prometheus.yml must exist")
        with open(self.prom_config_path, "r", encoding="utf-8") as f:
            prom_cfg = yaml.safe_load(f)

        self.assertIn("scrape_configs", prom_cfg)
        scrape_configs = prom_cfg["scrape_configs"]
        self.assertTrue(len(scrape_configs) >= 1)

        job = scrape_configs[0]
        self.assertEqual(job["metrics_path"], "/metrics")
        targets = job["static_configs"][0]["targets"]
        self.assertIn("tigergraph-agent:8000", targets)


if __name__ == "__main__":
    unittest.main()
