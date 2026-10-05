import re
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def normalize_figure_for_search(fig: str) -> list:
    """
    Generates candidate search tokens and unit-scaled conversions for a figure.
    Supports billions <-> millions, percentages, commas, currency symbols.
    """
    fig_clean = fig.strip().replace('\u202f', ' ').replace('\xa0', ' ')
    candidates = [fig_clean]
    
    # Extract numerical value and unit
    num_match = re.search(r'(\d+(?:,\d+)*(?:\.\d+)?)', fig_clean)
    if not num_match:
        return candidates
        
    num_str = num_match.group(1).replace(',', '')
    try:
        val = float(num_str)
    except ValueError:
        return candidates
        
    candidates.append(num_str)
    candidates.append(f"${num_str}")
    if '.' in num_str:
        candidates.append(f"${num_str.rstrip('0').rstrip('.')}")
    
    is_billion = bool(re.search(r'\b(?:billion|B)\b', fig_clean, re.IGNORECASE))
    is_million = bool(re.search(r'\b(?:million|M)\b', fig_clean, re.IGNORECASE))
    is_percent = '%' in fig_clean
    
    if is_billion:
        # Scale to millions
        millions_val = val * 1000.0
        # Exact integer
        candidates.append(f"{int(round(millions_val)):,}")
        candidates.append(f"{int(round(millions_val))}")
        candidates.append(f"${int(round(millions_val)):,}")
        candidates.append(f"${int(round(millions_val))}")
        # One decimal if fractional
        if not millions_val.is_integer():
            candidates.append(f"{millions_val:,.1f}")
            candidates.append(f"{millions_val:.1f}")
            
    elif is_million:
        # Scale to billions
        billions_val = val / 1000.0
        candidates.append(f"{billions_val:.1f}")
        candidates.append(f"{billions_val:.2f}")
        candidates.append(f"${billions_val:.1f}")
        candidates.append(f"${billions_val:.2f}")
        candidates.append(f"{int(round(val)):,}")
        candidates.append(f"{int(round(val))}")
        
    elif is_percent:
        candidates.append(f"{num_str}%")
        candidates.append(f"{num_str} %")
        if '.' in num_str:
            candidates.append(f"{float(num_str):.1f}%")
            
    return list(dict.fromkeys(candidates))

def match_figure_against_chunk_text(fig: str, chunk_text: str, tolerance: float = 0.05) -> bool:
    """
    Validates a financial figure against chunk text with:
    - String token match (comma-separated, decimals, currency symbols)
    - Unit scaling (billions in statement vs millions in SEC tables with rounding tolerance)
    - Calculated YoY growth match between adjacent period metrics
    """
    clean_chunk = chunk_text.replace('\u202f', ' ').replace('\xa0', ' ')
    
    # 1. Direct candidate token search
    tokens = normalize_figure_for_search(fig)
    for tok in tokens:
        # Whole word / number boundary check
        escaped = re.escape(tok)
        if re.search(rf'(?<!\d){escaped}(?!\d)', clean_chunk, re.IGNORECASE):
            return True
        if tok.lower() in clean_chunk.lower():
            return True

    # 2. Unit conversion with rounding tolerance (Billions in statement vs Millions in chunk)
    num_match = re.search(r'(\d+(?:,\d+)*(?:\.\d+)?)', fig)
    if not num_match:
        return False
    val_stated = float(num_match.group(1).replace(',', ''))
    
    is_billion = bool(re.search(r'\b(?:billion|B)\b', fig, re.IGNORECASE))
    is_million = bool(re.search(r'\b(?:million|M)\b', fig, re.IGNORECASE))
    is_percent = '%' in fig

    # Extract all candidate numbers from the chunk (integers and decimals)
    chunk_numbers = []
    for m in re.finditer(r'(?<!\w)(\d+(?:,\d+)*(?:\.\d+)?)(?!\w)', clean_chunk):
        raw_num = m.group(1).replace(',', '')
        try:
            chunk_numbers.append(float(raw_num))
        except ValueError:
            pass

    if is_billion:
        # Check if any chunk number in millions corresponds to val_stated in billions
        # e.g. 96,169 million -> 96.169 billion, rounds to 96.2 billion
        for cnum in chunk_numbers:
            cnum_in_billions = cnum / 1000.0
            # Matches if within rounding tolerance (e.g. |96.169 - 96.2| <= 0.05 or round == val_stated)
            if abs(round(cnum_in_billions, 1) - val_stated) < 1e-4 or abs(cnum_in_billions - val_stated) <= tolerance:
                return True
                
    elif is_million:
        for cnum in chunk_numbers:
            # Direct value match or scale
            if abs(cnum - val_stated) < 1e-4:
                return True
            if abs(cnum * 1000.0 - val_stated) < 1e-4:
                return True

    elif is_percent:
        # Check direct percentage values
        for cnum in chunk_numbers:
            if abs(cnum - val_stated) < 0.1: # 0.1% tolerance
                return True
        # Check if calculated growth rate between two numbers in chunk matches stated percentage
        # e.g. (96169 - 85200) / 85200 * 100 = 12.87% ≈ 12.9%
        for i in range(len(chunk_numbers)):
            for j in range(len(chunk_numbers)):
                if i != j and chunk_numbers[j] > 1000:
                    yoy = ((chunk_numbers[i] - chunk_numbers[j]) / chunk_numbers[j]) * 100.0
                    if abs(yoy - val_stated) <= 0.15 or abs(round(yoy, 1) - val_stated) < 1e-4:
                        return True

    return False

# Unit test suite
def run_tests():
    sample_sec_chunk = """
    | iPhone | $ 209,586 | $ 201,183 | $ 200,583 |
    | Mac | 33,708 | 29,984 | 29,357 |
    | iPad | 28,023 | 26,694 | 28,300 |
    | Wearables, Home and Accessories | 35,686 | 37,005 | 39,845 |
    | Services (1) | 109,158 | 96,169 | 85,200 |
    | Total net sales | $ 416,161 | $ 391,035 | $ 383,285 |
    Gross margin percentage: Services 75.4%, 73.9%, 70.8%.
    """

    tests = [
        ("85.2 billion", sample_sec_chunk, True, "85.2 billion vs 85,200 million"),
        ("$85.2 billion", sample_sec_chunk, True, "$85.2 billion vs 85,200 million"),
        ("96.2 billion", sample_sec_chunk, True, "96.2 billion vs 96,169 million (rounded)"),
        ("$96.2 billion", sample_sec_chunk, True, "$96.2 billion vs 96,169 million"),
        ("109.2 billion", sample_sec_chunk, True, "109.2 billion vs 109,158 million (rounded)"),
        ("$109.2 billion", sample_sec_chunk, True, "$109.2 billion vs 109,158 million"),
        ("12.9%", sample_sec_chunk, True, "12.9% calculated growth YoY (96,169 vs 85,200)"),
        ("13.5%", sample_sec_chunk, True, "13.5% calculated growth YoY (109,158 vs 96,169)"),
        ("75.4%", sample_sec_chunk, True, "75.4% direct gross margin percentage"),
        ("150.0 billion", sample_sec_chunk, False, "150.0 billion (incorrect figure, must reject)"),
        ("62.5%", sample_sec_chunk, False, "62.5% (incorrect percentage, must reject)"),
        ("$50,000", sample_sec_chunk, False, "$50,000 (incorrect dollar, must reject)")
    ]

    all_passed = True
    print("Running Verifier Unit Tests...")
    for fig, text, expected, desc in tests:
        res = match_figure_against_chunk_text(fig, text)
        passed = (res == expected)
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_passed = False
        print(f"[{status}] {desc}: got {res}, expected {expected}")

    print("\nOVERALL TEST RESULT:", "ALL PASSED" if all_passed else "SOME FAILED")
    return all_passed

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
