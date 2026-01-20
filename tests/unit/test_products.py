"""
Unit tests for product definitions.
"""

import pytest

from unified_ai.core.products import (
    ProductType,
    ProductConfig,
    get_product_config,
    list_products,
    PRODUCTS,
)


class TestProductType:
    """Tests for ProductType enum."""

    def test_product_values(self):
        """Test product enum values."""
        assert ProductType.CHATBOT.value == "chatbot"
        assert ProductType.WRITING_HELPER.value == "writing_helper"
        assert ProductType.CODE_REVIEWER.value == "code_reviewer"
        assert ProductType.SUPPORT_BOT.value == "support_bot"
        assert ProductType.CONTENT_SUMMARIZER.value == "content_summarizer"

    def test_all_products_have_configs(self):
        """Ensure all product types have configurations."""
        for product in ProductType:
            assert product in PRODUCTS
            config = PRODUCTS[product]
            assert isinstance(config, ProductConfig)


class TestProductConfig:
    """Tests for ProductConfig."""

    def test_config_has_required_fields(self):
        """Test that configs have required fields."""
        config = PRODUCTS[ProductType.CHATBOT]
        assert config.name
        assert config.description
        assert config.system_prompt
        assert config.version
        assert config.max_tokens > 0
        assert 0 <= config.temperature <= 2.0

    def test_system_prompts_not_empty(self):
        """Ensure all system prompts have content."""
        for product, config in PRODUCTS.items():
            assert len(config.system_prompt) > 50, f"{product} has empty/short system prompt"


class TestGetProductConfig:
    """Tests for get_product_config function."""

    def test_get_valid_product(self):
        """Test getting a valid product config."""
        config = get_product_config(ProductType.CODE_REVIEWER)
        assert config.name == "Code Reviewer"

    def test_get_invalid_product(self):
        """Test getting invalid product raises error."""
        with pytest.raises(KeyError):
            get_product_config("invalid")  # type: ignore


class TestListProducts:
    """Tests for list_products function."""

    def test_list_returns_all_products(self):
        """Test list returns all products."""
        products = list_products()
        assert len(products) == len(ProductType)

    def test_list_has_required_fields(self):
        """Test list items have required fields."""
        products = list_products()
        for product in products:
            assert "id" in product
            assert "name" in product
            assert "description" in product
            assert "version" in product
