#!/usr/bin/env python3
"""
Order parsing utilities for splitting multiple orders in a single string.
"""

import re
from typing import List


def split_orders(order_str: str) -> List[str]:
    """
    Split multiple orders in a single string using a simple and reliable approach.
    
    This approach uses regex to find order starts and then intelligently filters them.
    """
    if not order_str or not order_str.strip():
        return []
    
    order_str = order_str.strip()
    
    # Find all potential order starts using regex
    # Pattern matches: (A|F) followed by space and 3-letter province
    # Or: BUILD/DESTROY keywords
    pattern = r'\b([AF]\s+[A-Z]{3}|BUILD|DESTROY)\b'
    matches = list(re.finditer(pattern, order_str))
    
    if not matches:
        return [order_str] if order_str else []
    
    # Filter matches to only include actual order starts
    order_starts = []
    for i, match in enumerate(matches):
        start = match.start()
        match_text = match.group()
        
        # Check if this is an order start
        is_order_start = False
        
        if match_text in ['BUILD', 'DESTROY']:
            # BUILD/DESTROY are always order starts
            is_order_start = True
        elif start == 0:
            # At start of string
            is_order_start = True
        else:
            # Check if we're after a space and not in middle of support/convoy
            if order_str[start-1] == ' ':
                # Look backwards to see if we're in support/convoy
                before_text = order_str[:start]
                
                # Simple heuristic: if we see 'S' or 'C' in the recent text,
                # and this unit appears right after it, we're in support/convoy
                # Also check if we're in BUILD/DESTROY orders
                in_support_or_convoy = False
                in_build_destroy = False
                
                # Check if we're in BUILD/DESTROY order
                if 'BUILD' in before_text or 'DESTROY' in before_text:
                    # Find the last BUILD or DESTROY
                    build_pos = before_text.rfind('BUILD')
                    destroy_pos = before_text.rfind('DESTROY')
                    last_pos = max(build_pos, destroy_pos)
                    
                    if last_pos != -1:
                        # Check if this unit appears after the BUILD/DESTROY
                        if match_text in order_str:
                            # Find all occurrences of this unit
                            unit_positions = [m.start() for m in re.finditer(r'\b' + re.escape(match_text) + r'\b', order_str)]
                            # Check if any occurrence is after the BUILD/DESTROY
                            for pos in unit_positions:
                                if pos > last_pos:
                                    in_build_destroy = True
                                    break
                
                # Check for support pattern: UNIT S UNIT
                if ' S ' in before_text:
                    # Find the last 'S' and see what comes after
                    s_pos = before_text.rfind(' S ')
                    after_s = before_text[s_pos + 3:].strip()
                    
                    # If after 'S' we have a unit+province, we're in support
                    if len(after_s) >= 5 and after_s[0] in 'AF' and after_s[1] == ' ':
                        # Check if this is followed by action or end
                        if len(after_s) == 5 or (len(after_s) > 5 and after_s[5] in ' H-'):
                            # We're in support, check if this is the target unit
                            if after_s.startswith(match_text):
                                in_support_or_convoy = True
                    elif len(after_s) == 0:
                        # Empty after S - check if this unit is the target
                        # Look at the full order to see if this unit appears after the S
                        if match_text in order_str:
                            # Find all occurrences of this unit
                            unit_positions = [m.start() for m in re.finditer(r'\b' + re.escape(match_text) + r'\b', order_str)]
                            # Check if any occurrence is after the S
                            for pos in unit_positions:
                                if pos > s_pos:
                                    in_support_or_convoy = True
                                    break
                
                # Check for convoy pattern: UNIT C UNIT
                if ' C ' in before_text:
                    # Find the last 'C' and see what comes after
                    c_pos = before_text.rfind(' C ')
                    after_c = before_text[c_pos + 3:].strip()
                    
                    # If after 'C' we have a unit+province, we're in convoy
                    if len(after_c) >= 5 and after_c[0] in 'AF' and after_c[1] == ' ':
                        # Check if this is followed by action or end
                        if len(after_c) == 5 or (len(after_c) > 5 and after_c[5] in ' H-'):
                            # We're in convoy, check if this is the target unit
                            if after_c.startswith(match_text):
                                in_support_or_convoy = True
                    elif len(after_c) == 0:
                        # Empty after C - check if this unit is the target
                        if match_text in order_str:
                            # Find all occurrences of this unit
                            unit_positions = [m.start() for m in re.finditer(r'\b' + re.escape(match_text) + r'\b', order_str)]
                            # Check if any occurrence is after the C
                            for pos in unit_positions:
                                if pos > c_pos:
                                    in_support_or_convoy = True
                                    break
                
                if not in_support_or_convoy and not in_build_destroy:
                    is_order_start = True
        
        if is_order_start:
            order_starts.append(start)
    
    # Extract orders based on start positions
    orders = []
    for i, start in enumerate(order_starts):
        end = order_starts[i+1] if i+1 < len(order_starts) else len(order_str)
        order = order_str[start:end].strip()
        if order:
            orders.append(order)
    
    return orders


def test_order_splitting():
    """Test the order splitting function with various cases."""
    
    # Basic orders
    assert split_orders("A ROM - TUS") == ["A ROM - TUS"]
    assert split_orders("A ROM - TUS A VEN H") == ["A ROM - TUS", "A VEN H"]
    
    # Support orders (critical!)
    assert split_orders("A ROM S A VEN H") == ["A ROM S A VEN H"]
    assert split_orders("F NAP S A ROM - TUS") == ["F NAP S A ROM - TUS"]
    assert split_orders("A ROM S A VEN H A TUS - PIE") == [
        "A ROM S A VEN H", 
        "A TUS - PIE"
    ]
    
    # Mixed orders
    assert split_orders("A ROM - TUS F NAP - ROM A VEN S A ROM H") == [
        "A ROM - TUS",
        "F NAP - ROM", 
        "A VEN S A ROM H"
    ]
    
    # Convoy orders
    assert split_orders("F ION C A ROM - TUN") == ["F ION C A ROM - TUN"]
    assert split_orders("F ION C A ROM - TUN A VEN H") == [
        "F ION C A ROM - TUN",
        "A VEN H"
    ]
    
    # Build/Destroy
    assert split_orders("BUILD A PAR") == ["BUILD A PAR"]
    assert split_orders("DESTROY A ROM") == ["DESTROY A ROM"]
    assert split_orders("BUILD A PAR DESTROY A ROM") == ["BUILD A PAR", "DESTROY A ROM"]
    
    # Edge cases
    assert split_orders("") == []
    assert split_orders("   ") == []
    assert split_orders("A ROM") == ["A ROM"]  # Incomplete order
    
    # Complex support orders
    assert split_orders("A ROM S A VEN - TUS F NAP S A ROM H") == [
        "A ROM S A VEN - TUS",
        "F NAP S A ROM H"
    ]
    
    print("✅ All order splitting tests passed!")


if __name__ == "__main__":
    test_order_splitting()