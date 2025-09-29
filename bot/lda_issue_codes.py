"""Official LDA issue codes and descriptions."""

import logging
from typing import Dict, List
from .database import DatabaseManager

logger = logging.getLogger(__name__)

# Official LDA issue codes from the Senate Lobbying Disclosure database
OFFICIAL_ISSUE_CODES = {
    "ACC": "Accounting",
    "ADV": "Advertising",
    "AER": "Aeronautics and Space",
    "AGR": "Agriculture",
    "ALC": "Alcohol and Drug Abuse",
    "ANI": "Animals",
    "APP": "Apparel/Clothing Industry/Textiles",
    "ART": "Arts/Entertainment",
    "AUT": "Automotive Industry",
    "AVI": "Aviation/Airlines/Airports",
    "BAN": "Banking",
    "BNK": "Bankruptcy",
    "BEV": "Beverage Industry",
    "BUD": "Budget/Appropriations",
    "CHM": "Chemicals/Chemical Industry",
    "CIV": "Civil Rights/Civil Liberties",
    "CAW": "Clean Air and Water (Quality)",
    "CDT": "Commodities (Big Ticket)",
    "COM": "Communications/Broadcasting/Radio/TV",
    "CPI": "Computer Industry",
    "CSP": "Consumer Issues/Safety/Protection",
    "CON": "Constitution",
    "CPT": "Copyright/Patent/Trademark",
    "DEF": "Defense",
    "DOC": "District of Columbia",
    "DIS": "Disaster Planning/Emergencies",
    "ECN": "Economics/Economic Development",
    "EDU": "Education",
    "ENG": "Energy/Nuclear",
    "ENV": "Environmental/Superfund",
    "FAM": "Family Issues/Abortion/Adoption",
    "FIR": "Firearms/Guns/Ammunition",
    "FIN": "Financial Institutions/Investments/Securities",
    "FOO": "Food Industry (Safety, Labeling, etc.)",
    "FOR": "Foreign Relations",
    "FUE": "Fuel/Gas/Oil",
    "GAM": "Gaming/Gambling/Casino",
    "GOV": "Government Issues",
    "HCR": "Health Issues",
    "HOM": "Homeland Security",
    "HOU": "Housing",
    "IMM": "Immigration",
    "IND": "Indian/Native American Affairs",
    "INS": "Insurance",
    "INT": "Intelligence and Surveillance",
    "LBR": "Labor Issues/Antitrust/Workplace",
    "LAW": "Law Enforcement/Crime/Criminal Justice",
    "MAN": "Manufacturing",
    "MAR": "Marine/Maritime/Boating/Fisheries",
    "MED": "Medical/Disease Research/Clinical Labs",
    "MMM": "Medicare/Medicaid",
    "MON": "Minting/Money/Gold Standard",
    "NAT": "Natural Resources",
    "PHA": "Pharmacy",
    "POS": "Postal",
    "RRR": "Railroads",
    "RES": "Real Estate/Land Use/Conservation",
    "REL": "Religion",
    "RET": "Retirement",
    "ROD": "Roads/Highway",
    "SCI": "Science/Technology",
    "SMB": "Small Business",
    "SPO": "Sports/Athletics",
    "TAX": "Taxation/Internal Revenue Code",
    "TEC": "Telecommunications",
    "TOB": "Tobacco",
    "TOR": "Torts",
    "TRD": "Trade (Domestic and Foreign)",
    "TRA": "Transportation",
    "TOU": "Travel/Tourism",
    "TRU": "Trucking/Shipping",
    "URB": "Urban Development/Municipalities",
    "UNM": "Unemployment",
    "UTI": "Utilities",
    "VET": "Veterans",
    "WAS": "Waste (Hazardous/Solid/Interstate/Nuclear)",
    "WEL": "Welfare"
}


def seed_issue_codes(db_manager: DatabaseManager) -> int:
    """Seed the issue codes table with official LDA codes.
    
    Args:
        db_manager: Database manager instance
        
    Returns:
        Number of issue codes inserted/updated
    """
    logger.info("Seeding official LDA issue codes")
    
    inserted_count = 0
    updated_count = 0
    
    with db_manager.get_connection() as conn:
        for code, description in OFFICIAL_ISSUE_CODES.items():
            try:
                # Check if we're using PostgreSQL or SQLite
                try:
                    # Try PostgreSQL syntax first
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO issue (code, description) 
                        VALUES (%s, %s)
                        ON CONFLICT (code) DO UPDATE SET 
                            description = EXCLUDED.description
                        RETURNING (xmax = 0) AS inserted
                    """, (code, description))
                    
                    result = cursor.fetchone()
                    if result and result[0]:
                        inserted_count += 1
                    else:
                        updated_count += 1
                        
                except Exception:
                    # Fall back to SQLite syntax
                    cursor = conn.execute("SELECT id FROM issue WHERE code = ?", (code,))
                    existing = cursor.fetchone()
                    
                    if existing:
                        conn.execute("""
                            UPDATE issue SET description = ? WHERE code = ?
                        """, (description, code))
                        updated_count += 1
                    else:
                        conn.execute("""
                            INSERT INTO issue (code, description) VALUES (?, ?)
                        """, (code, description))
                        inserted_count += 1
                        
            except Exception as e:
                logger.error(f"Failed to insert/update issue code {code}: {e}")
        
        if hasattr(conn, 'commit'):
            conn.commit()
    
    logger.info(f"Issue codes seeded: {inserted_count} inserted, {updated_count} updated")
    return inserted_count + updated_count


def get_issue_description(code: str) -> str:
    """Get the description for an issue code.
    
    Args:
        code: Issue code (e.g., "HCR")
        
    Returns:
        Description or the code itself if not found
    """
    return OFFICIAL_ISSUE_CODES.get(code.upper(), code)


def get_all_issue_codes() -> Dict[str, str]:
    """Get all official issue codes and descriptions.
    
    Returns:
        Dictionary mapping codes to descriptions
    """
    return OFFICIAL_ISSUE_CODES.copy()


def format_issue_codes(codes: List[str]) -> str:
    """Format a list of issue codes for display.
    
    Args:
        codes: List of issue codes
        
    Returns:
        Formatted string with codes and descriptions
    """
    if not codes:
        return "—"
    
    # Show up to 3 codes with descriptions, then "• +N more"
    formatted_codes = []
    for code in codes[:3]:
        desc = get_issue_description(code)
        if desc != code:
            formatted_codes.append(f"{code}")
        else:
            formatted_codes.append(code)
    
    result = " • ".join(formatted_codes)
    
    if len(codes) > 3:
        result += f" • +{len(codes) - 3} more"
    
    return result
