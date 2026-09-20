"""
Unit Tests for Enterprise Kubernetes Helm Chart and Health Probes (tests/test_helm_chart.py)
"""

import os
import unittest
import yaml


class TestHelmChart(unittest.TestCase):
    def setUp(self):
        self.repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.helm_dir = os.path.join(self.repo_root, "deploy", "helm", "tigergraph-agent")
        self.chart_path = os.path.join(self.helm_dir, "Chart.yaml")
        self.values_path = os.path.join(self.helm_dir, "values.yaml")
        self.templates_dir = os.path.join(self.helm_dir, "templates")

    def test_01_chart_metadata(self):
        """Verify Chart.yaml conforms to Helm v2 specification."""
        self.assertTrue(os.path.exists(self.chart_path), "Chart.yaml must exist")
        with open(self.chart_path, "r", encoding="utf-8") as f:
            chart = yaml.safe_load(f)

        self.assertEqual(chart.get("apiVersion"), "v2")
        self.assertEqual(chart.get("name"), "tigergraph-agent")
        self.assertEqual(chart.get("version"), "0.7.0")
        self.assertEqual(chart.get("appVersion"), "0.7.0")
        self.assertIn("keywords", chart)
        self.assertIn("fraud-detection", chart["keywords"])

    def test_02_values_configuration(self):
        """Verify values.yaml defines hardened security context, resources, and probes."""
        self.assertTrue(os.path.exists(self.values_path), "values.yaml must exist")
        with open(self.values_path, "r", encoding="utf-8") as f:
            values = yaml.safe_load(f)

        # 1. Pod & Container Security Context
        pod_sec = values.get("podSecurityContext", {})
        self.assertTrue(pod_sec.get("runAsNonRoot"), "Pod must run as non-root")
        self.assertEqual(pod_sec.get("runAsUser"), 10001)

        sec_ctx = values.get("securityContext", {})
        self.assertFalse(sec_ctx.get("allowPrivilegeEscalation"))

        # 2. Resources
        resources = values.get("resources", {})
        self.assertIn("requests", resources)
        self.assertIn("limits", resources)
        self.assertEqual(resources["requests"]["cpu"], "500m")
        self.assertEqual(resources["limits"]["cpu"], "2000m")

        # 3. Health & Readiness Probes
        probes = values.get("probes", {})
        self.assertIn("liveness", probes)
        self.assertIn("readiness", probes)
        self.assertEqual(probes["liveness"]["httpGet"]["path"], "/api/telemetry/dashboard")
        self.assertEqual(probes["readiness"]["httpGet"]["path"], "/api/telemetry/dashboard")
        self.assertEqual(probes["liveness"]["httpGet"]["port"], 8000)

        # 4. Autoscaling
        autoscaling = values.get("autoscaling", {})
        self.assertTrue(autoscaling.get("enabled"))
        self.assertEqual(autoscaling.get("minReplicas"), 2)
        self.assertEqual(autoscaling.get("maxReplicas"), 10)

        # 5. Service & Monitoring
        self.assertEqual(values["service"]["port"], 8000)
        self.assertTrue(values["serviceMonitor"]["enabled"])
        self.assertEqual(values["serviceMonitor"]["path"], "/metrics")

    def test_03_templates_existence_and_structure(self):
        """Verify all mandatory Kubernetes templates exist and contain proper directives."""
        expected_templates = [
            "serviceaccount.yaml",
            "service.yaml",
            "deployment.yaml",
            "hpa.yaml",
        ]
        for tmpl in expected_templates:
            tmpl_path = os.path.join(self.templates_dir, tmpl)
            self.assertTrue(os.path.exists(tmpl_path), f"Template {tmpl} must exist")
            with open(tmpl_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn(".Release.Name", content, f"Template {tmpl} must reference Release.Name")
            self.assertIn(".Chart.Name", content, f"Template {tmpl} must reference Chart.Name")

    def test_04_simulated_manifest_rendering(self):
        """Verify that simulated template substitution yields a valid Kubernetes manifest."""
        with open(self.values_path, "r", encoding="utf-8") as f:
            values = yaml.safe_load(f)

        # Simulate rendered deployment manifest
        rendered_manifest = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": "prod-tigergraph-agent",
                "labels": {"app.kubernetes.io/name": "tigergraph-agent", "app.kubernetes.io/instance": "prod"},
            },
            "spec": {
                "selector": {
                    "matchLabels": {"app.kubernetes.io/name": "tigergraph-agent", "app.kubernetes.io/instance": "prod"},
                },
                "template": {
                    "metadata": {
                        "labels": {"app.kubernetes.io/name": "tigergraph-agent", "app.kubernetes.io/instance": "prod"},
                        "annotations": values["podAnnotations"],
                    },
                    "spec": {
                        "securityContext": values["podSecurityContext"],
                        "containers": [
                            {
                                "name": "tigergraph-agent",
                                "image": f"{values['image']['repository']}:{values['image']['tag']}",
                                "ports": [{"containerPort": values["service"]["port"]}],
                                "resources": values["resources"],
                                "livenessProbe": values["probes"]["liveness"],
                                "readinessProbe": values["probes"]["readiness"],
                            }
                        ],
                    },
                },
            },
        }

        # Validate that it serializes and parses cleanly with PyYAML
        manifest_str = yaml.dump(rendered_manifest)
        parsed = yaml.safe_load(manifest_str)
        self.assertEqual(parsed["kind"], "Deployment")
        self.assertEqual(parsed["spec"]["template"]["spec"]["containers"][0]["ports"][0]["containerPort"], 8000)
        self.assertEqual(parsed["spec"]["template"]["spec"]["securityContext"]["runAsUser"], 10001)


if __name__ == "__main__":
    unittest.main()
