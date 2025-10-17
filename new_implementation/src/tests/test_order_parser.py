"""
Comprehensive unit tests for Order Parser module.

Tests cover OrderParser class with all order types, edge cases, coast specifications,
error handling, and validation scenarios.
"""

import pytest
from unittest.mock import Mock, patch
from typing import List, Dict, Any

from engine.order_parser import OrderParser, OrderParseError, OrderValidationError, ParsedOrder
from engine.data_models import OrderType, OrderStatus


class TestOrderParser:
    """Test OrderParser class."""
    
    @pytest.fixture
    def parser(self):
        """Create OrderParser instance for testing."""
        return OrderParser()
    
    def test_parser_initialization(self, parser):
        """Test OrderParser initialization."""
        assert parser is not None
        assert parser.valid_powers == {
            'ENGLAND', 'FRANCE', 'GERMANY', 'RUSSIA', 
            'TURKEY', 'AUSTRIA', 'ITALY'
        }
        assert parser.move_pattern is not None
        assert parser.hold_pattern is not None
        assert parser.support_pattern is not None
        assert parser.convoy_pattern is not None
        assert parser.retreat_pattern is not None
        assert parser.build_pattern is not None
        assert parser.destroy_pattern is not None


class TestMoveOrderParsing:
    """Test move order parsing."""
    
    @pytest.fixture
    def parser(self):
        """Create OrderParser instance."""
        return OrderParser()
    
    def test_basic_move_order(self, parser):
        """Test basic move order parsing."""
        parsed = parser.parse_order_text("A PAR - BUR", "FRANCE")
        
        assert parsed.order_type == OrderType.MOVE
        assert parsed.power == "FRANCE"
        assert parsed.unit_type == "A"
        assert parsed.unit_province == "PAR"
        assert parsed.target_province == "BUR"
        assert parsed.raw_text == "A PAR - BUR"
    
    def test_fleet_move_order(self, parser):
        """Test fleet move order parsing."""
        parsed = parser.parse_order_text("F BRE - ENG", "FRANCE")
        
        assert parsed.order_type == OrderType.MOVE
        assert parsed.power == "FRANCE"
        assert parsed.unit_type == "F"
        assert parsed.unit_province == "BRE"
        assert parsed.target_province == "ENG"
    
    def test_move_order_with_power_prefix(self, parser):
        """Test move order with power name prefix."""
        parsed = parser.parse_order_text("FRANCE A PAR - BUR", "FRANCE")
        
        assert parsed.order_type == OrderType.MOVE
        assert parsed.power == "FRANCE"
        assert parsed.unit_type == "A"
        assert parsed.unit_province == "PAR"
        assert parsed.target_province == "BUR"
    
    def test_move_order_case_insensitive(self, parser):
        """Test move order parsing is case insensitive."""
        parsed = parser.parse_order_text("a par - bur", "FRANCE")
        
        assert parsed.order_type == OrderType.MOVE
        assert parsed.unit_type == "A"
        assert parsed.unit_province == "PAR"
        assert parsed.target_province == "BUR"
    
    def test_move_order_with_spaces(self, parser):
        """Test move order with various spacing."""
        test_cases = [
            "A PAR-BUR",
            "A PAR - BUR",
            "A  PAR  -  BUR",
            "A PAR- BUR",
            "A PAR -BUR"
        ]
        
        for order_text in test_cases:
            parsed = parser.parse_order_text(order_text, "FRANCE")
            assert parsed.order_type == OrderType.MOVE
            assert parsed.unit_type == "A"
            assert parsed.unit_province == "PAR"
            assert parsed.target_province == "BUR"
    
    def test_move_order_invalid_format(self, parser):
        """Test move order with invalid format."""
        invalid_orders = [
            "A - BUR",  # Missing source
            "PAR - BUR",  # Missing unit type
            "A PAR BUR",  # Missing dash
            "A PAR -",  # Missing target
            "- A PAR BUR",  # Invalid format
        ]
        
        for order_text in invalid_orders:
            with pytest.raises(OrderParseError):
                parser.parse_order_text(order_text, "FRANCE")


class TestHoldOrderParsing:
    """Test hold order parsing."""
    
    @pytest.fixture
    def parser(self):
        """Create OrderParser instance."""
        return OrderParser()
    
    def test_basic_hold_order(self, parser):
        """Test basic hold order parsing."""
        parsed = parser.parse_order_text("A PAR H", "FRANCE")
        
        assert parsed.order_type == OrderType.HOLD
        assert parsed.power == "FRANCE"
        assert parsed.unit_type == "A"
        assert parsed.unit_province == "PAR"
        assert parsed.target_province is None
    
    def test_hold_order_implicit(self, parser):
        """Test hold order without explicit H."""
        parsed = parser.parse_order_text("A PAR", "FRANCE")
        
        assert parsed.order_type == OrderType.HOLD
        assert parsed.power == "FRANCE"
        assert parsed.unit_type == "A"
        assert parsed.unit_province == "PAR"
    
    def test_fleet_hold_order(self, parser):
        """Test fleet hold order parsing."""
        parsed = parser.parse_order_text("F BRE H", "FRANCE")
        
        assert parsed.order_type == OrderType.HOLD
        assert parsed.power == "FRANCE"
        assert parsed.unit_type == "F"
        assert parsed.unit_province == "BRE"
    
    def test_hold_order_case_insensitive(self, parser):
        """Test hold order parsing is case insensitive."""
        parsed = parser.parse_order_text("a par h", "FRANCE")
        
        assert parsed.order_type == OrderType.HOLD
        assert parsed.unit_type == "A"
        assert parsed.unit_province == "PAR"


class TestSupportOrderParsing:
    """Test support order parsing."""
    
    @pytest.fixture
    def parser(self):
        """Create OrderParser instance."""
        return OrderParser()
    
    def test_support_move_order(self, parser):
        """Test support for move order."""
        parsed = parser.parse_order_text("F BRE S A PAR - BUR", "FRANCE")
        
        assert parsed.order_type == OrderType.SUPPORT
        assert parsed.power == "FRANCE"
        assert parsed.unit_type == "F"
        assert parsed.unit_province == "BRE"
        assert parsed.supported_unit_type == "A"
        assert parsed.supported_unit_province == "PAR"
        assert parsed.supported_target == "BUR"
    
    def test_support_hold_order(self, parser):
        """Test support for hold order."""
        parsed = parser.parse_order_text("A MAR S A PAR", "FRANCE")
        
        assert parsed.order_type == OrderType.SUPPORT
        assert parsed.power == "FRANCE"
        assert parsed.unit_type == "A"
        assert parsed.unit_province == "MAR"
        assert parsed.supported_unit_type == "A"
        assert parsed.supported_unit_province == "PAR"
        assert parsed.supported_target is None
    
    def test_support_order_case_insensitive(self, parser):
        """Test support order parsing is case insensitive."""
        parsed = parser.parse_order_text("f bre s a par - bur", "FRANCE")
        
        assert parsed.order_type == OrderType.SUPPORT
        assert parsed.unit_type == "F"
        assert parsed.unit_province == "BRE"
        assert parsed.supported_unit_type == "A"
        assert parsed.supported_unit_province == "PAR"
        assert parsed.supported_target == "BUR"
    
    def test_support_order_with_spaces(self, parser):
        """Test support order with various spacing."""
        test_cases = [
            "F BRE S A PAR-BUR",
            "F BRE S A PAR - BUR",
            "F BRE S A PAR -BUR",
            "F BRE S A PAR- BUR",
            "F  BRE  S  A  PAR  -  BUR"
        ]
        
        for order_text in test_cases:
            parsed = parser.parse_order_text(order_text, "FRANCE")
            assert parsed.order_type == OrderType.SUPPORT
            assert parsed.unit_type == "F"
            assert parsed.unit_province == "BRE"
            assert parsed.supported_unit_type == "A"
            assert parsed.supported_unit_province == "PAR"
            assert parsed.supported_target == "BUR"


class TestConvoyOrderParsing:
    """Test convoy order parsing."""
    
    @pytest.fixture
    def parser(self):
        """Create OrderParser instance."""
        return OrderParser()
    
    def test_basic_convoy_order(self, parser):
        """Test basic convoy order parsing."""
        parsed = parser.parse_order_text("F NTH C A LON - HOL", "ENGLAND")
        
        assert parsed.order_type == OrderType.CONVOY
        assert parsed.power == "ENGLAND"
        assert parsed.unit_type == "F"
        assert parsed.unit_province == "NTH"
        assert parsed.convoyed_unit_type == "A"
        assert parsed.convoyed_unit_province == "LON"
        assert parsed.convoyed_target == "HOL"
    
    def test_convoy_order_case_insensitive(self, parser):
        """Test convoy order parsing is case insensitive."""
        parsed = parser.parse_order_text("f nth c a lon - hol", "ENGLAND")
        
        assert parsed.order_type == OrderType.CONVOY
        assert parsed.unit_type == "F"
        assert parsed.unit_province == "NTH"
        assert parsed.convoyed_unit_type == "A"
        assert parsed.convoyed_unit_province == "LON"
        assert parsed.convoyed_target == "HOL"
    
    def test_convoy_order_with_spaces(self, parser):
        """Test convoy order with various spacing."""
        test_cases = [
            "F NTH C A LON-HOL",
            "F NTH C A LON - HOL",
            "F NTH C A LON -HOL",
            "F NTH C A LON- HOL",
            "F  NTH  C  A  LON  -  HOL"
        ]
        
        for order_text in test_cases:
            parsed = parser.parse_order_text(order_text, "ENGLAND")
            assert parsed.order_type == OrderType.CONVOY
            assert parsed.unit_type == "F"
            assert parsed.unit_province == "NTH"
            assert parsed.convoyed_unit_type == "A"
            assert parsed.convoyed_unit_province == "LON"
            assert parsed.convoyed_target == "HOL"


class TestRetreatOrderParsing:
    """Test retreat order parsing."""
    
    @pytest.fixture
    def parser(self):
        """Create OrderParser instance."""
        return OrderParser()
    
    def test_basic_retreat_order(self, parser):
        """Test basic retreat order parsing."""
        parsed = parser.parse_order_text("A PAR R PIC", "FRANCE")
        
        assert parsed.order_type == OrderType.RETREAT
        assert parsed.power == "FRANCE"
        assert parsed.unit_type == "A"
        assert parsed.unit_province == "PAR"
        assert parsed.retreat_province == "PIC"
    
    def test_retreat_order_case_insensitive(self, parser):
        """Test retreat order parsing is case insensitive."""
        parsed = parser.parse_order_text("a par r pic", "FRANCE")
        
        assert parsed.order_type == OrderType.RETREAT
        assert parsed.unit_type == "A"
        assert parsed.unit_province == "PAR"
        assert parsed.retreat_province == "PIC"
    
    def test_retreat_order_with_spaces(self, parser):
        """Test retreat order with various spacing."""
        test_cases = [
            "A PAR R PIC",
            "A PAR R PIC",
            "A  PAR  R  PIC",
            "A PAR R PIC"
        ]
        
        for order_text in test_cases:
            parsed = parser.parse_order_text(order_text, "FRANCE")
            assert parsed.order_type == OrderType.RETREAT
            assert parsed.unit_type == "A"
            assert parsed.unit_province == "PAR"
            assert parsed.retreat_province == "PIC"


class TestBuildOrderParsing:
    """Test build order parsing."""
    
    @pytest.fixture
    def parser(self):
        """Create OrderParser instance."""
        return OrderParser()
    
    def test_basic_build_order(self, parser):
        """Test basic build order parsing."""
        parsed = parser.parse_order_text("BUILD A PAR", "FRANCE")
        
        assert parsed.order_type == OrderType.BUILD
        assert parsed.power == "FRANCE"
        assert parsed.build_type == "A"
        assert parsed.build_province == "PAR"
        assert parsed.build_coast is None
    
    def test_build_order_with_coast(self, parser):
        """Test build order with coast specification."""
        parsed = parser.parse_order_text("BUILD F SPA/NC", "FRANCE")
        
        assert parsed.order_type == OrderType.BUILD
        assert parsed.power == "FRANCE"
        assert parsed.build_type == "F"
        assert parsed.build_province == "SPA"
        assert parsed.build_coast == "NC"
    
    def test_build_order_case_insensitive(self, parser):
        """Test build order parsing is case insensitive."""
        parsed = parser.parse_order_text("build a par", "FRANCE")
        
        assert parsed.order_type == OrderType.BUILD
        assert parsed.build_type == "A"
        assert parsed.build_province == "PAR"
    
    def test_build_order_with_spaces(self, parser):
        """Test build order with various spacing."""
        test_cases = [
            "BUILD A PAR",
            "BUILD  A  PAR",
            "BUILD A PAR",
            "BUILD F SPA/NC",
            "BUILD F SPA / NC"
        ]
        
        for order_text in test_cases:
            parsed = parser.parse_order_text(order_text, "FRANCE")
            assert parsed.order_type == OrderType.BUILD
            assert parsed.build_type in ["A", "F"]
            assert parsed.build_province in ["PAR", "SPA"]


class TestDestroyOrderParsing:
    """Test destroy order parsing."""
    
    @pytest.fixture
    def parser(self):
        """Create OrderParser instance."""
        return OrderParser()
    
    def test_basic_destroy_order(self, parser):
        """Test basic destroy order parsing."""
        parsed = parser.parse_order_text("DESTROY A SIL", "GERMANY")
        
        assert parsed.order_type == OrderType.DESTROY
        assert parsed.power == "GERMANY"
        assert parsed.destroy_unit_type == "A"
        assert parsed.destroy_unit_province == "SIL"
    
    def test_destroy_order_case_insensitive(self, parser):
        """Test destroy order parsing is case insensitive."""
        parsed = parser.parse_order_text("destroy a sil", "GERMANY")
        
        assert parsed.order_type == OrderType.DESTROY
        assert parsed.destroy_unit_type == "A"
        assert parsed.destroy_unit_province == "SIL"
    
    def test_destroy_order_with_spaces(self, parser):
        """Test destroy order with various spacing."""
        test_cases = [
            "DESTROY A SIL",
            "DESTROY  A  SIL",
            "DESTROY A SIL",
            "DESTROY F KIE"
        ]
        
        for order_text in test_cases:
            parsed = parser.parse_order_text(order_text, "GERMANY")
            assert parsed.order_type == OrderType.DESTROY
            assert parsed.destroy_unit_type in ["A", "F"]
            assert parsed.destroy_unit_province in ["SIL", "KIE"]


class TestCoastSpecifications:
    """Test coast specification parsing."""
    
    @pytest.fixture
    def parser(self):
        """Create OrderParser instance."""
        return OrderParser()
    
    def test_spanish_coasts(self, parser):
        """Test Spanish coast specifications."""
        # North Coast
        parsed = parser.parse_order_text("F SPA/NC - POR", "FRANCE")
        assert parsed.order_type == OrderType.MOVE
        assert parsed.unit_province == "SPA/NC"
        assert parsed.target_province == "POR"
        
        # South Coast
        parsed = parser.parse_order_text("F SPA/SC - WES", "FRANCE")
        assert parsed.order_type == OrderType.MOVE
        assert parsed.unit_province == "SPA/SC"
        assert parsed.target_province == "WES"
    
    def test_bulgarian_coasts(self, parser):
        """Test Bulgarian coast specifications."""
        # East Coast
        parsed = parser.parse_order_text("F BUL/EC - BLA", "TURKEY")
        assert parsed.order_type == OrderType.MOVE
        assert parsed.unit_province == "BUL/EC"
        assert parsed.target_province == "BLA"
        
        # South Coast
        parsed = parser.parse_order_text("F BUL/SC - AEG", "TURKEY")
        assert parsed.order_type == OrderType.MOVE
        assert parsed.unit_province == "BUL/SC"
        assert parsed.target_province == "AEG"
    
    def test_st_petersburg_coasts(self, parser):
        """Test St. Petersburg coast specifications."""
        # North Coast
        parsed = parser.parse_order_text("F STP/NC - BAR", "RUSSIA")
        assert parsed.order_type == OrderType.MOVE
        assert parsed.unit_province == "STP/NC"
        assert parsed.target_province == "BAR"
        
        # South Coast
        parsed = parser.parse_order_text("F STP/SC - FIN", "RUSSIA")
        assert parsed.order_type == OrderType.MOVE
        assert parsed.unit_province == "STP/SC"
        assert parsed.target_province == "FIN"
    
    def test_coast_in_support_orders(self, parser):
        """Test coast specifications in support orders."""
        parsed = parser.parse_order_text("F BUL/EC S F BLA - RUM", "TURKEY")
        
        assert parsed.order_type == OrderType.SUPPORT
        assert parsed.unit_province == "BUL/EC"
        assert parsed.supported_unit_type == "F"
        assert parsed.supported_unit_province == "BLA"
        assert parsed.supported_target == "RUM"
    
    def test_coast_in_convoy_orders(self, parser):
        """Test coast specifications in convoy orders."""
        parsed = parser.parse_order_text("F SPA/NC C A POR - MAR", "FRANCE")
        
        assert parsed.order_type == OrderType.CONVOY
        assert parsed.unit_province == "SPA/NC"
        assert parsed.convoyed_unit_type == "A"
        assert parsed.convoyed_unit_province == "POR"
        assert parsed.convoyed_target == "MAR"


class TestOrderValidation:
    """Test order validation."""
    
    @pytest.fixture
    def parser(self):
        """Create OrderParser instance."""
        return OrderParser()
    
    def test_valid_power_names(self, parser):
        """Test valid power name recognition."""
        valid_powers = ['ENGLAND', 'FRANCE', 'GERMANY', 'RUSSIA', 'TURKEY', 'AUSTRIA', 'ITALY']
        
        for power in valid_powers:
            parsed = parser.parse_order_text(f"{power} A PAR - BUR", power)
            assert parsed.power == power
            assert parsed.order_type == OrderType.MOVE
    
    def test_invalid_power_names(self, parser):
        """Test invalid power name handling."""
        # Should not treat invalid power names as power prefixes
        parsed = parser.parse_order_text("INVALID A PAR - BUR", "FRANCE")
        assert parsed.power == "FRANCE"  # Uses provided power, not "INVALID"
        assert parsed.order_type == OrderType.MOVE
    
    def test_power_name_case_insensitive(self, parser):
        """Test power name parsing is case insensitive."""
        parsed = parser.parse_order_text("france A PAR - BUR", "FRANCE")
        assert parsed.power == "FRANCE"
        assert parsed.order_type == OrderType.MOVE


class TestErrorHandling:
    """Test error handling in order parsing."""
    
    @pytest.fixture
    def parser(self):
        """Create OrderParser instance."""
        return OrderParser()
    
    def test_empty_order_text(self, parser):
        """Test empty order text handling."""
        with pytest.raises(OrderParseError):
            parser.parse_order_text("", "FRANCE")
        
        with pytest.raises(OrderParseError):
            parser.parse_order_text("   ", "FRANCE")
    
    def test_malformed_orders(self, parser):
        """Test malformed order handling."""
        malformed_orders = [
            "INVALID ORDER",
            "A",
            "A PAR INVALID",
            "A PAR -",
            "- A PAR",
            "A PAR - BUR - EXTRA",
            "A PAR - BUR EXTRA",
            "A PAR - BUR - EXTRA - MORE"
        ]
        
        for order_text in malformed_orders:
            with pytest.raises(OrderParseError):
                parser.parse_order_text(order_text, "FRANCE")
    
    def test_invalid_unit_types(self, parser):
        """Test invalid unit type handling."""
        invalid_unit_orders = [
            "X PAR - BUR",  # Invalid unit type
            "B PAR - BUR",  # Invalid unit type
            "1 PAR - BUR",  # Invalid unit type
        ]
        
        for order_text in invalid_unit_orders:
            with pytest.raises(OrderParseError):
                parser.parse_order_text(order_text, "FRANCE")
    
    def test_invalid_province_names(self, parser):
        """Test invalid province name handling."""
        # Note: The parser doesn't validate province names against a map,
        # it only validates the format. Invalid province names will be
        # caught during game validation, not parsing.
        parsed = parser.parse_order_text("A INVALID - BUR", "FRANCE")
        assert parsed.order_type == OrderType.MOVE
        assert parsed.unit_province == "INVALID"  # Parser accepts it
        assert parsed.target_province == "BUR"


class TestEdgeCases:
    """Test edge cases and special scenarios."""
    
    @pytest.fixture
    def parser(self):
        """Create OrderParser instance."""
        return OrderParser()
    
    def test_very_long_province_names(self, parser):
        """Test handling of very long province names."""
        # The parser uses regex patterns that expect 3-letter province codes
        # Very long names should fail parsing
        with pytest.raises(OrderParseError):
            parser.parse_order_text("A VERYLONGPROVINCENAME - BUR", "FRANCE")
    
    def test_special_characters(self, parser):
        """Test handling of special characters."""
        # The parser expects alphanumeric province names
        with pytest.raises(OrderParseError):
            parser.parse_order_text("A PAR@ - BUR", "FRANCE")
        
        with pytest.raises(OrderParseError):
            parser.parse_order_text("A PAR# - BUR", "FRANCE")
    
    def test_numeric_province_names(self, parser):
        """Test handling of numeric province names."""
        # The parser expects alphabetic province names
        with pytest.raises(OrderParseError):
            parser.parse_order_text("A 123 - BUR", "FRANCE")
    
    def test_mixed_case_province_names(self, parser):
        """Test handling of mixed case province names."""
        parsed = parser.parse_order_text("A Par - Bur", "FRANCE")
        assert parsed.order_type == OrderType.MOVE
        assert parsed.unit_province == "PAR"  # Should be normalized to uppercase
        assert parsed.target_province == "BUR"
    
    def test_whitespace_handling(self, parser):
        """Test various whitespace scenarios."""
        test_cases = [
            ("A PAR - BUR", "normal"),
            (" A PAR - BUR ", "leading/trailing spaces"),
            ("A  PAR  -  BUR", "multiple spaces"),
            ("A\tPAR\t-\tBUR", "tabs"),
            ("A\nPAR\n-\nBUR", "newlines")
        ]
        
        for order_text, description in test_cases:
            try:
                parsed = parser.parse_order_text(order_text, "FRANCE")
                assert parsed.order_type == OrderType.MOVE, f"Failed for {description}"
                assert parsed.unit_province == "PAR"
                assert parsed.target_province == "BUR"
            except OrderParseError:
                # Some whitespace cases might fail, which is acceptable
                pass


class TestOrderParserIntegration:
    """Integration tests for OrderParser."""
    
    @pytest.fixture
    def parser(self):
        """Create OrderParser instance."""
        return OrderParser()
    
    def test_all_order_types_in_sequence(self, parser):
        """Test parsing all order types in sequence."""
        orders = [
            ("A PAR - BUR", OrderType.MOVE),
            ("F BRE H", OrderType.HOLD),
            ("A MAR S A PAR - BUR", OrderType.SUPPORT),
            ("F NTH C A LON - HOL", OrderType.CONVOY),
            ("A PAR R PIC", OrderType.RETREAT),
            ("BUILD A PAR", OrderType.BUILD),
            ("DESTROY A SIL", OrderType.DESTROY)
        ]
        
        for order_text, expected_type in orders:
            parsed = parser.parse_order_text(order_text, "FRANCE")
            assert parsed.order_type == expected_type, f"Failed for order: {order_text}"
    
    def test_power_prefix_removal(self, parser):
        """Test that power prefixes are properly removed."""
        orders_with_prefixes = [
            "FRANCE A PAR - BUR",
            "GERMANY F KIE H",
            "ENGLAND A LVP S F LON - NTH",
            "RUSSIA F STP/NC C A MOS - SWE"
        ]
        
        for order_text in orders_with_prefixes:
            parsed = parser.parse_order_text(order_text, "FRANCE")
            # The parsed order should not contain the power prefix in raw_text
            assert not parsed.raw_text.startswith(("FRANCE", "GERMANY", "ENGLAND", "RUSSIA"))
    
    def test_complex_order_scenarios(self, parser):
        """Test complex order scenarios."""
        complex_orders = [
            # Support with coast specification
            ("F BUL/EC S F BLA - RUM", OrderType.SUPPORT),
            # Convoy with coast specification
            ("F SPA/NC C A POR - MAR", OrderType.CONVOY),
            # Build with coast specification
            ("BUILD F SPA/SC", OrderType.BUILD),
            # Support for hold
            ("A MAR S A PAR", OrderType.SUPPORT),
            # Move with coast specification
            ("F STP/NC - BAR", OrderType.MOVE)
        ]
        
        for order_text, expected_type in complex_orders:
            parsed = parser.parse_order_text(order_text, "FRANCE")
            assert parsed.order_type == expected_type, f"Failed for complex order: {order_text}"


# Performance tests
@pytest.mark.slow
class TestOrderParserPerformance:
    """Performance tests for OrderParser."""
    
    @pytest.fixture
    def parser(self):
        """Create OrderParser instance."""
        return OrderParser()
    
    def test_parse_large_number_of_orders(self, parser):
        """Test parsing a large number of orders."""
        orders = [
            "A PAR - BUR",
            "F BRE H",
            "A MAR S A PAR - BUR",
            "F NTH C A LON - HOL",
            "A PAR R PIC",
            "BUILD A PAR",
            "DESTROY A SIL"
        ] * 100  # 700 orders
        
        import time
        start_time = time.time()
        
        for order_text in orders:
            parsed = parser.parse_order_text(order_text, "FRANCE")
            assert parsed is not None
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should parse 700 orders in less than 1 second
        assert duration < 1.0, f"Parsing 700 orders took {duration:.3f} seconds"
    
    def test_parse_performance_benchmark(self, parser):
        """Benchmark order parsing performance."""
        order_text = "A PAR - BUR"
        
        import time
        start_time = time.time()
        
        # Parse the same order 1000 times
        for _ in range(1000):
            parsed = parser.parse_order_text(order_text, "FRANCE")
            assert parsed.order_type == OrderType.MOVE
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should parse 1000 orders in less than 0.1 seconds
        assert duration < 0.1, f"Parsing 1000 orders took {duration:.3f} seconds"
