"""Tests for WorkflowRegistry.

Run: pytest tests/test_registry.py -v
"""
import pytest
from pathlib import Path

from spl3.registry import LocalRegistry, FederatedRegistry, WorkflowDefinition, RegistryError


COOKBOOK_DIR = Path(__file__).parent.parent / "cookbook" / "code_pipeline"


class TestLocalRegistry:

    def test_register_and_get(self):
        registry = LocalRegistry()
        defn = WorkflowDefinition(
            name="my_workflow",
            source_file="test.spl",
            ast_node=object(),
        )
        registry.register(defn)
        result = registry.get("my_workflow")
        assert result.name == "my_workflow"

    def test_get_unknown_raises(self):
        registry = LocalRegistry()
        with pytest.raises(RegistryError, match="Unknown workflow"):
            registry.get("nonexistent")

    def test_has(self):
        registry = LocalRegistry()
        assert not registry.has("foo")
        registry.register(WorkflowDefinition("foo", "f.spl", None))
        assert registry.has("foo")

    def test_list(self):
        registry = LocalRegistry()
        registry.register(WorkflowDefinition("b_workflow", "b.spl", None))
        registry.register(WorkflowDefinition("a_workflow", "a.spl", None))
        assert registry.list() == ["a_workflow", "b_workflow"]

    def test_overwrite_warns(self, caplog):
        import logging
        registry = LocalRegistry()
        defn1 = WorkflowDefinition("wf", "file1.spl", None)
        defn2 = WorkflowDefinition("wf", "file2.spl", None)
        registry.register(defn1)
        with caplog.at_level(logging.WARNING, logger="spl3.registry"):
            registry.register(defn2)
        assert "overwriting" in caplog.text

    def test_load_file(self):
        """Load real .spl files from the cookbook directory."""
        registry = LocalRegistry()
        if not (COOKBOOK_DIR / "generate_code.spl").exists():
            pytest.skip("Example files not found")
        count = registry.load_file(COOKBOOK_DIR / "generate_code.spl")
        assert count == 1
        assert registry.has("generate_code")

    def test_load_dir(self):
        """Load all .spl files from the cookbook directory."""
        registry = LocalRegistry()
        if not COOKBOOK_DIR.exists():
            pytest.skip("Examples directory not found")
        count = registry.load_dir(COOKBOOK_DIR)
        assert count >= 3   # generate_code, review_code, improve_code at minimum
        assert registry.has("generate_code")
        assert registry.has("review_code")
        assert registry.has("improve_code")

    def test_load_nonexistent_raises(self):
        registry = LocalRegistry()
        with pytest.raises(RegistryError, match="File not found"):
            registry.load_file("/nonexistent/path.spl")


class TestFederatedRegistry:

    def test_local_hit_no_hub_call(self):
        local = LocalRegistry()
        local.register(WorkflowDefinition("local_wf", "l.spl", None))

        class NeverCalledHub:
            def get(self, name):
                raise AssertionError("Hub should not be called for local workflow")
            def has(self, name):
                return False

        registry = FederatedRegistry(local, NeverCalledHub())
        result = registry.get("local_wf")
        assert result.name == "local_wf"

    def test_hub_fallback_on_miss(self):
        local = LocalRegistry()

        class MockHub:
            def get(self, name):
                if name == "remote_wf":
                    return WorkflowDefinition("remote_wf", "hub://remote_wf", None)
                raise RegistryError(f"Unknown: {name}")
            def has(self, name):
                return name == "remote_wf"
            def list(self):
                return ["remote_wf"]

        registry = FederatedRegistry(local, MockHub())
        result = registry.get("remote_wf")
        assert result.name == "remote_wf"

    def test_miss_everywhere_raises(self):
        local = LocalRegistry()

        class EmptyHub:
            def get(self, name):
                raise RegistryError(f"Not on Hub: {name}")
            def has(self, name):
                return False
            def list(self):
                return []

        registry = FederatedRegistry(local, EmptyHub())
        with pytest.raises(RegistryError):
            registry.get("ghost_workflow")
