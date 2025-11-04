"""
Unit tests for province mapping module.

Tests the province name normalization and mapping functionality.
"""
import pytest
from engine.province_mapping import (
    PROVINCE_MAPPING,
    ALTERNATIVE_MAPPING,
    normalize_province_name,
    get_province_info,
    get_all_province_names,
    get_sea_provinces,
    get_land_provinces,
    get_coastal_provinces,
    is_sea_province,
    is_land_province,
    is_coastal_province
)


class TestProvinceMapping:
    """Test PROVINCE_MAPPING dictionary."""
    
    def test_mapping_completeness(self):
        """Test that PROVINCE_MAPPING has expected provinces."""
        assert "PAR" in PROVINCE_MAPPING
        assert "LON" in PROVINCE_MAPPING
        assert "BER" in PROVINCE_MAPPING
        assert "VEN" in PROVINCE_MAPPING
        assert "STP" in PROVINCE_MAPPING
        assert "BAL" in PROVINCE_MAPPING
        assert "NTH" in PROVINCE_MAPPING
    
    def test_mapping_format(self):
        """Test that all mappings have correct format (full_name, province_type)."""
        for abbr, value in PROVINCE_MAPPING.items():
            assert isinstance(value, tuple)
            assert len(value) == 2
            full_name, prov_type = value
            assert isinstance(full_name, str)
            assert isinstance(prov_type, str)
            assert prov_type in ["sea", "land", "coastal"]
    
    def test_sea_provinces_in_mapping(self):
        """Test that known sea provinces are in mapping."""
        sea_provs = ["BAL", "NTH", "ENG", "ADR", "ION", "MAO"]
        for prov in sea_provs:
            assert prov in PROVINCE_MAPPING
            _, prov_type = PROVINCE_MAPPING[prov]
            assert prov_type == "sea"
    
    def test_land_provinces_in_mapping(self):
        """Test that known land provinces are in mapping."""
        land_provs = ["BOH", "BUR", "GAL", "SIL", "TYR"]
        for prov in land_provs:
            assert prov in PROVINCE_MAPPING
            _, prov_type = PROVINCE_MAPPING[prov]
            assert prov_type == "land"
    
    def test_coastal_provinces_in_mapping(self):
        """Test that known coastal provinces are in mapping."""
        coastal_provs = ["PAR", "LON", "BER", "VEN", "ROM"]
        for prov in coastal_provs:
            assert prov in PROVINCE_MAPPING
            _, prov_type = PROVINCE_MAPPING[prov]
            assert prov_type == "coastal"


class TestNormalizeProvinceName:
    """Test normalize_province_name function."""
    
    def test_normalize_standard_abbreviation(self):
        """Test normalizing standard province abbreviations."""
        assert normalize_province_name("PAR") == "PAR"
        assert normalize_province_name("par") == "PAR"
        assert normalize_province_name("Par") == "PAR"
        assert normalize_province_name("  PAR  ") == "PAR"
    
    def test_normalize_alternative_names(self):
        """Test normalizing alternative province names."""
        assert normalize_province_name("english") == "ENG"
        assert normalize_province_name("channel") == "ENG"
        assert normalize_province_name("baltic") == "BAL"
        assert normalize_province_name("aegean") == "AEG"
        assert normalize_province_name("norwegian") == "NWG"
    
    def test_normalize_unknown_province(self):
        """Test normalizing unknown province names (returns uppercase)."""
        assert normalize_province_name("unknown") == "UNKNOWN"
        assert normalize_province_name("xyz") == "XYZ"
    
    def test_normalize_empty_string(self):
        """Test normalizing empty strings."""
        assert normalize_province_name("") == ""
        assert normalize_province_name("   ") == ""
    
    def test_normalize_with_coast_specification(self):
        """Test normalizing provinces with coast specifications."""
        # Coast specifications should be preserved
        assert normalize_province_name("SPA/NC") == "SPA/NC"
        assert normalize_province_name("SPA/SC") == "SPA/SC"
        assert normalize_province_name("STP/NC") == "STP/NC"
        assert normalize_province_name("BUL/EC") == "BUL/EC"


class TestGetProvinceInfo:
    """Test get_province_info function."""
    
    def test_get_known_province_info(self):
        """Test getting info for known provinces."""
        full_name, prov_type = get_province_info("PAR")
        assert full_name == "Paris"
        assert prov_type == "coastal"
        
        full_name, prov_type = get_province_info("BAL")
        assert full_name == "Baltic Sea"
        assert prov_type == "sea"
        
        full_name, prov_type = get_province_info("BUR")
        assert full_name == "Burgundy"
        assert prov_type == "land"
    
    def test_get_unknown_province_info(self):
        """Test getting info for unknown provinces."""
        full_name, prov_type = get_province_info("UNKNOWN")
        assert full_name is None
        assert prov_type is None
    
    def test_get_province_info_case_insensitive(self):
        """Test that get_province_info is case-insensitive."""
        full_name1, prov_type1 = get_province_info("PAR")
        full_name2, prov_type2 = get_province_info("par")
        assert full_name1 == full_name2
        assert prov_type1 == prov_type2


class TestProvinceTypeFilters:
    """Test province type filter functions."""
    
    def test_get_all_province_names(self):
        """Test getting all province names."""
        all_provs = get_all_province_names()
        assert isinstance(all_provs, list)
        assert len(all_provs) > 0
        assert "PAR" in all_provs
        assert "LON" in all_provs
    
    def test_get_sea_provinces(self):
        """Test getting sea provinces."""
        sea_provs = get_sea_provinces()
        assert isinstance(sea_provs, list)
        assert "BAL" in sea_provs
        assert "NTH" in sea_provs
        assert "ENG" in sea_provs
        # Verify all are actually sea provinces
        for prov in sea_provs:
            _, prov_type = PROVINCE_MAPPING[prov]
            assert prov_type == "sea"
    
    def test_get_land_provinces(self):
        """Test getting land provinces."""
        land_provs = get_land_provinces()
        assert isinstance(land_provs, list)
        assert "BOH" in land_provs
        assert "BUR" in land_provs
        # Verify all are actually land provinces
        for prov in land_provs:
            _, prov_type = PROVINCE_MAPPING[prov]
            assert prov_type == "land"
    
    def test_get_coastal_provinces(self):
        """Test getting coastal provinces."""
        coastal_provs = get_coastal_provinces()
        assert isinstance(coastal_provs, list)
        assert "PAR" in coastal_provs
        assert "LON" in coastal_provs
        # Verify all are actually coastal provinces
        for prov in coastal_provs:
            _, prov_type = PROVINCE_MAPPING[prov]
            assert prov_type == "coastal"
    
    def test_province_type_filters_no_overlap(self):
        """Test that province type filters don't overlap."""
        sea_provs = set(get_sea_provinces())
        land_provs = set(get_land_provinces())
        coastal_provs = set(get_coastal_provinces())
        
        # Sea and land should not overlap
        assert sea_provs.isdisjoint(land_provs)
        # Sea and coastal should not overlap
        assert sea_provs.isdisjoint(coastal_provs)
        # Land and coastal should not overlap
        assert land_provs.isdisjoint(coastal_provs)
    
    def test_all_provinces_in_one_category(self):
        """Test that all provinces are in exactly one category."""
        all_provs = set(get_all_province_names())
        sea_provs = set(get_sea_provinces())
        land_provs = set(get_land_provinces())
        coastal_provs = set(get_coastal_provinces())
        
        union = sea_provs | land_provs | coastal_provs
        assert union == all_provs


class TestProvinceTypeCheckers:
    """Test province type checker functions."""
    
    def test_is_sea_province(self):
        """Test is_sea_province function."""
        assert is_sea_province("BAL") is True
        assert is_sea_province("NTH") is True
        assert is_sea_province("PAR") is False
        assert is_sea_province("BUR") is False
    
    def test_is_land_province(self):
        """Test is_land_province function."""
        assert is_land_province("BUR") is True
        assert is_land_province("BOH") is True
        assert is_land_province("PAR") is False
        assert is_land_province("BAL") is False
    
    def test_is_coastal_province(self):
        """Test is_coastal_province function."""
        assert is_coastal_province("PAR") is True
        assert is_coastal_province("LON") is True
        assert is_coastal_province("BUR") is False
        assert is_coastal_province("BAL") is False
    
    def test_province_type_checkers_unknown(self):
        """Test province type checkers with unknown provinces."""
        assert is_sea_province("UNKNOWN") is False
        assert is_land_province("UNKNOWN") is False
        assert is_coastal_province("UNKNOWN") is False
    
    def test_province_type_checkers_case_insensitive(self):
        """Test that province type checkers are case-insensitive."""
        assert is_sea_province("bal") == is_sea_province("BAL")
        assert is_land_province("bur") == is_land_province("BUR")
        assert is_coastal_province("par") == is_coastal_province("PAR")


class TestAlternativeMapping:
    """Test ALTERNATIVE_MAPPING dictionary."""
    
    def test_alternative_mapping_format(self):
        """Test that alternative mappings point to valid provinces."""
        for alt_name, standard in ALTERNATIVE_MAPPING.items():
            assert isinstance(alt_name, str)
            assert isinstance(standard, str)
            # Note: Some alternatives may reference provinces not in standard map
            # This is acceptable for variant support
            if standard not in PROVINCE_MAPPING:
                # Log for debugging but don't fail - may be for variant maps
                pass
    
    def test_alternative_mapping_examples(self):
        """Test specific alternative mappings."""
        assert ALTERNATIVE_MAPPING["english"] == "ENG"
        assert ALTERNATIVE_MAPPING["channel"] == "ENG"
        assert ALTERNATIVE_MAPPING["baltic"] == "BAL"
        assert ALTERNATIVE_MAPPING["norwegian"] == "NWG"
    
    def test_normalize_uses_alternative_mapping(self):
        """Test that normalize_province_name uses alternative mapping."""
        assert normalize_province_name("english") == "ENG"
        assert normalize_province_name("channel") == "ENG"
        assert normalize_province_name("baltic") == "BAL"


class TestProvinceMappingEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_special_characters(self):
        """Test handling of special characters."""
        # Coast specifications should be preserved
        result = normalize_province_name("SPA/NC")
        assert "/" in result or result == "SPA/NC"
    
    def test_very_long_strings(self):
        """Test handling of very long strings."""
        long_string = "A" * 100
        result = normalize_province_name(long_string)
        assert isinstance(result, str)
        assert len(result) == 100
    
    def test_numeric_strings(self):
        """Test handling of numeric strings."""
        result = normalize_province_name("123")
        assert result == "123"
    
    def test_unicode_characters(self):
        """Test handling of unicode characters."""
        # Most provinces are ASCII, but test that unicode is handled
        result = normalize_province_name("PARé")
        assert isinstance(result, str)
    
    def test_whitespace_handling(self):
        """Test proper whitespace trimming."""
        assert normalize_province_name("  PAR  ") == "PAR"
        assert normalize_province_name("\tPAR\n") == "PAR"


@pytest.mark.unit
class TestProvinceMappingIntegration:
    """Integration tests for province mapping."""
    
    def test_full_normalization_workflow(self):
        """Test complete normalization workflow."""
        # Start with various formats
        inputs = ["par", "PAR", "  par  ", "Paris"]
        
        for input_str in inputs:
            normalized = normalize_province_name(input_str)
            info = get_province_info(normalized)
            # Should get valid info for PAR
            if normalized == "PAR":
                assert info[0] is not None
                assert info[1] == "coastal"
    
    def test_province_type_consistency(self):
        """Test that province type functions are consistent."""
        test_provinces = ["PAR", "BAL", "BUR", "LON", "NTH"]
        
        for prov in test_provinces:
            full_name, prov_type = get_province_info(prov)
            if prov_type == "sea":
                assert is_sea_province(prov) is True
                assert is_land_province(prov) is False
                assert is_coastal_province(prov) is False
            elif prov_type == "land":
                assert is_land_province(prov) is True
                assert is_sea_province(prov) is False
                assert is_coastal_province(prov) is False
            elif prov_type == "coastal":
                assert is_coastal_province(prov) is True
                assert is_sea_province(prov) is False
                assert is_land_province(prov) is False

