
import requests
import sqlite3
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Union
import os

# Setup logging
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/collection.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# API endpoints
OPENFDA_BASE_URL = "https://api.fda.gov/drug/label.json"
RXNORM_BASE_URL = "https://rxnav.nlm.nih.gov/REST"

# OpenFDA API Key (replace with your actual key or use environment variable)
OPENFDA_API_KEY = os.environ.get("OPENFDA_API_KEY", "jcb0VZsIN2LfFqif5Ua0vJoy36g0u885ckm4pmUx") # <<< ADD THIS LINE

# Common medications list (50+ drugs)
COMMON_DRUGS = [
    "Metformin", "Aspirin", "Ibuprofen", "Amoxicillin", "Lisinopril",
    "Atorvastatin", "Omeprazole", "Amlodipine", "Levothyroxine", "Simvastatin",
    "Losartan", "Gabapentin", "Hydrochlorothiazide", "Metoprolol", "Sertraline",
    "Albuterol", "Furosemide", "Acetaminophen", "Warfarin", "Prednisone",
    "Clopidogrel", "Escitalopram", "Montelukast", "Rosuvastatin", "Pantoprazole",
    "Fluticasone", "Tramadol", "Citalopram", "Carvedilol", "Pravastatin",
    "Tamsulosin", "Loratadine", "Bupropion", "Venlafaxine", "Meloxicam",
    "Doxycycline", "Ciprofloxacin", "Azithromycin", "Cephalexin", "Clonazepam",
    "Cyclobenzaprine", "Ranitidine", "Trazodone", "Duloxetine", "Insulin",
    "Naproxen", "Diazepam", "Potassium", "Famotidine", "Sildenafil",
    "Alprazolam", "Cetirizine", "Diphenhydramine", "Morphine", "Methylphenidate"
]


class DrugDataCollector:
    """Main class for collecting pharmaceutical data"""
    
    def __init__(self, db_path: str = "data/drugs.db"):
        self.db_path = db_path
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'DrugDataCollector/1.0'})
        os.makedirs('data', exist_ok=True)
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database with schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # NOTE: 'side_effects' is stored as a JSON string to keep the dict structure
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS drugs (
                drug_id TEXT PRIMARY KEY,
                drug_name TEXT NOT NULL UNIQUE,
                generic_name TEXT,
                brand_names TEXT,
                drug_class TEXT,
                indications TEXT,
                mechanism_of_action TEXT,
                dosage_forms TEXT,
                common_dosages TEXT,
                side_effects TEXT, 
                contraindications TEXT,
                drug_interactions TEXT,
                data_sources TEXT,
                last_updated TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info(f"Database initialized at {self.db_path}")
    
    def fetch_from_openfda(self, drug_name: str, retries: int = 3) -> Optional[Dict]:
        """
        Fetch drug data from OpenFDA API
        
        Args:
            drug_name: Name of the drug
            retries: Number of retry attempts
            
        Returns:
            Dictionary with drug data or None
        """
        for attempt in range(retries):
            try:
                # Search by generic or brand name
                params = {
                    'search': f'openfda.generic_name:"{drug_name}" openfda.brand_name:"{drug_name}"',
                    'limit': 1,
                    'api_key': OPENFDA_API_KEY # <<< USE THE API KEY HERE
                }
                
                response = self.session.get(OPENFDA_BASE_URL, params=params, timeout=10)
                
                # Handle rate limiting
                if response.status_code == 429:
                    wait_time = 2 ** attempt
                    logger.warning(f"Rate limited. Waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                
                response.raise_for_status()
                data = response.json()
                
                if 'results' in data and len(data['results']) > 0:
                    result = data['results'][0]
                    logger.info(f"✓ Fetched {drug_name} from OpenFDA")
                    return self._parse_openfda_response(result, drug_name)
                else:
                    logger.warning(f"No results for {drug_name} in OpenFDA")
                    return None
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Error fetching {drug_name} from OpenFDA (attempt {attempt+1}): {e}")
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                    
        return None
    
    def _flatten_and_clean_list(self, lst: Optional[Union[List, str]]) -> List[str]:
        """Flattens a potentially nested list of strings, removes empty, strips whitespace, and makes unique."""
        if not lst:
            return []
        
        flat_list = []
        if isinstance(lst, str):
            if lst.strip():
                flat_list.append(lst.strip())
        elif isinstance(lst, list):
            for item in lst:
                if isinstance(item, list):
                    flat_list.extend([s.strip() for s in item if isinstance(s, str) and s.strip()])
                elif isinstance(item, str) and item.strip():
                    flat_list.append(item.strip())
        return list(set(flat_list)) # Remove duplicates

    def _parse_openfda_response(self, data: Dict, drug_name: str) -> Dict:
        """Parse OpenFDA API response"""
        openfda = data.get('openfda', {})
        
        return {
            'drug_name': drug_name,
            'generic_name': self._flatten_and_clean_list(openfda.get('generic_name', [None]))[0] if self._flatten_and_clean_list(openfda.get('generic_name', [None])) else None,
            'brand_names': self._flatten_and_clean_list(openfda.get('brand_name', [])),
            'drug_class': self._flatten_and_clean_list(openfda.get('pharm_class_epc', [None]))[0] if self._flatten_and_clean_list(openfda.get('pharm_class_epc', [None])) else None,
            'indications': self._flatten_and_clean_list(data.get('indications_and_usage', [])),
            'mechanism_of_action': self._flatten_and_clean_list(data.get('mechanism_of_action', [])),
            'dosage_forms': self._flatten_and_clean_list(openfda.get('dosage_form', [])),
            'side_effects': {
                'common': self._flatten_and_clean_list(data.get('adverse_reactions', [])),
                'serious': self._flatten_and_clean_list(data.get('boxed_warning', []))
            },
            'contraindications': self._flatten_and_clean_list(data.get('contraindications', [])),
            'drug_interactions': self._flatten_and_clean_list(data.get('drug_interactions', [])),
            'data_source': 'OpenFDA' # Will be converted to list in merge
        }
    
    def fetch_from_rxnorm(self, drug_name: str, retries: int = 3) -> Optional[Dict]:
        """
        Fetch drug data from RxNorm API
        
        Args:
            drug_name: Name of the drug
            retries: Number of retry attempts
            
        Returns:
            Dictionary with drug data or None
        """
        for attempt in range(retries):
            try:
                # Get RxCUI for drug
                url = f"{RXNORM_BASE_URL}/rxcui.json"
                params = {'name': drug_name}
                
                response = self.session.get(url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                rxcui_list = data.get('idGroup', {}).get('rxnormId', [])
                if not rxcui_list:
                    logger.warning(f"No RxCUI found for {drug_name}")
                    return None
                
                rxcui = rxcui_list[0]
                
                # Get drug properties
                properties_url = f"{RXNORM_BASE_URL}/rxcui/{rxcui}/properties.json"
                prop_response = self.session.get(properties_url, timeout=10)
                prop_response.raise_for_status()
                prop_data = prop_response.json()
                
                logger.info(f"✓ Fetched {drug_name} from RxNorm")
                return self._parse_rxnorm_response(prop_data, rxcui, drug_name)
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Error fetching {drug_name} from RxNorm (attempt {attempt+1}): {e}")
                if attempt < retries - 1:
                    time.sleep(1)
                    
        return None
    
    def _parse_rxnorm_response(self, data: Dict, rxcui: str, drug_name: str) -> Dict:
        """Parse RxNorm API response"""
        properties = data.get('properties', {})
        
        return {
            'rxcui': rxcui, # <<< ADDED RXCUI HERE
            'drug_name': drug_name,
            'generic_name': properties.get('name', drug_name),
            'data_source': 'RxNorm'
        }
    
    def merge_drug_data(self, openfda_data: Optional[Dict], 
                       rxnorm_data: Optional[Dict], 
                       drug_name: str) -> Dict:
        """
        Merge data from multiple sources
        
        Args:
            openfda_data: Data from OpenFDA
            rxnorm_data: Data from RxNorm
            drug_name: Original drug name
            
        Returns:
            Merged drug data dictionary
        """
        merged = {
            'drug_id': None, # Will be set below
            'drug_name': drug_name,
            'generic_name': None,
            'brand_names': [],
            'drug_class': None,
            'indications': [],
            'mechanism_of_action': [], # Changed from None to [] for consistency with list fields
            'dosage_forms': [],
            'common_dosages': [], # This field is currently not populated by APIs
            'side_effects': {'common': [], 'serious': []},
            'contraindications': [],
            'drug_interactions': [],
            'data_sources': [],
            'last_updated': datetime.now().isoformat()
        }
        
        # Merge OpenFDA data
        if openfda_data:
            merged['generic_name'] = openfda_data.get('generic_name') or merged['generic_name'] # Prioritize OpenFDA for generic if exists
            merged['brand_names'].extend(openfda_data.get('brand_names', []))
            merged['drug_class'] = openfda_data.get('drug_class') or merged['drug_class']
            merged['indications'].extend(openfda_data.get('indications', []))
            # Ensure mechanism_of_action is merged as a list
            if isinstance(openfda_data.get('mechanism_of_action'), list):
                merged['mechanism_of_action'].extend(openfda_data['mechanism_of_action'])
            elif isinstance(openfda_data.get('mechanism_of_action'), str):
                merged['mechanism_of_action'].append(openfda_data['mechanism_of_action'])

            merged['dosage_forms'].extend(openfda_data.get('dosage_forms', []))
            merged['side_effects']['common'].extend(openfda_data['side_effects'].get('common', []))
            merged['side_effects']['serious'].extend(openfda_data['side_effects'].get('serious', []))
            merged['contraindications'].extend(openfda_data.get('contraindications', []))
            merged['drug_interactions'].extend(openfda_data.get('drug_interactions', []))
            merged['data_sources'].append('OpenFDA')
        
        # Merge RxNorm data (for standardization)
        if rxnorm_data:
            # RxNorm's generic name is often very canonical, so prioritize if OpenFDA didn't provide
            merged['generic_name'] = rxnorm_data.get('generic_name') or merged['generic_name']
            # RxNorm might provide a drug_class as well, if OpenFDA didn't
            # merged['drug_class'] = rxnorm_data.get('drug_class') or merged['drug_class'] # RxNorm property does not include drug_class consistently
            merged['data_sources'].append('RxNorm')

        # Clean up lists and make unique after merging
        merged['brand_names'] = list(set(filter(None, merged['brand_names'])))
        merged['indications'] = list(set(filter(None, merged['indications'])))
        merged['mechanism_of_action'] = list(set(filter(None, merged['mechanism_of_action'])))
        merged['dosage_forms'] = list(set(filter(None, merged['dosage_forms'])))
        merged['side_effects']['common'] = list(set(filter(None, merged['side_effects']['common'])))
        merged['side_effects']['serious'] = list(set(filter(None, merged['side_effects']['serious'])))
        merged['contraindications'] = list(set(filter(None, merged['contraindications'])))
        merged['drug_interactions'] = list(set(filter(None, merged['drug_interactions'])))
        merged['data_sources'] = list(set(filter(None, merged['data_sources']))) # Ensure unique sources

        # Set drug_id: prefer RxCUI if available, otherwise use a derived name-based ID
        if rxnorm_data and rxnorm_data.get('rxcui'):
            merged['drug_id'] = f"rxcui_{rxnorm_data['rxcui']}"
        else:
            merged['drug_id'] = f"drug_{drug_name.lower().replace(' ', '_')}"
        
        return merged
    
    def save_to_database(self, drug_data: Dict):
        """
        Save drug data to SQLite database
        
        Args:
            drug_data: Dictionary containing drug information
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Prepare data for insertion, converting lists/dicts to JSON strings
            data_to_insert = {
                'drug_id': drug_data['drug_id'],
                'drug_name': drug_data['drug_name'],
                'generic_name': drug_data['generic_name'],
                'brand_names': json.dumps(drug_data['brand_names']),
                'drug_class': drug_data['drug_class'],
                'indications': json.dumps(drug_data['indications']),
                'mechanism_of_action': json.dumps(drug_data['mechanism_of_action']),
                'dosage_forms': json.dumps(drug_data['dosage_forms']),
                'common_dosages': json.dumps(drug_data['common_dosages']), # Still an empty list, but correctly formatted
                'side_effects': json.dumps(drug_data['side_effects']), # Stores as {'common':[], 'serious':[]}
                'contraindications': json.dumps(drug_data['contraindications']),
                'drug_interactions': json.dumps(drug_data['drug_interactions']),
                'data_sources': json.dumps(drug_data['data_sources']),
                'last_updated': drug_data['last_updated']
            }

            columns = ', '.join(data_to_insert.keys())
            placeholders = ', '.join('?' * len(data_to_insert))
            values = tuple(data_to_insert.values())

            cursor.execute(f'''
                INSERT OR REPLACE INTO drugs ({columns})
                VALUES ({placeholders})
            ''', values)
            
            conn.commit()
            logger.info(f"✓ Saved {drug_data['drug_name']} to database with ID: {drug_data['drug_id']}")
            
        except sqlite3.Error as e:
            logger.error(f"Database error for {drug_data['drug_name']}: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def collect_drug(self, drug_name: str):
        """
        Collect data for a single drug from all sources
        
        Args:
            drug_name: Name of the drug to collect
        """
        logger.info(f"Starting collection for: {drug_name}")
        
        # Fetch from both sources
        openfda_data = self.fetch_from_openfda(drug_name)
        time.sleep(0.5)  # Rate limiting
        
        rxnorm_data = self.fetch_from_rxnorm(drug_name)
        time.sleep(0.5)  # Rate limiting
        
        # Merge and save
        merged_data = self.merge_drug_data(openfda_data, rxnorm_data, drug_name)
        self.save_to_database(merged_data)
        
        return merged_data
    
    def collect_all_drugs(self, drug_list: List[str], batch_size: int = 10):
        """
        Collect data for all drugs in batches
        
        Args:
            drug_list: List of drug names
            batch_size: Number of drugs to process before checkpoint
        """
        total = len(drug_list)
        successful = 0
        failed = 0
        
        logger.info(f"Starting collection for {total} drugs...")
        
        for i, drug_name in enumerate(drug_list, 1):
            try:
                self.collect_drug(drug_name)
                successful += 1
                
                # Progress update
                if i % batch_size == 0:
                    logger.info(f"Progress: {i}/{total} drugs processed")
                    logger.info(f"✓ Successful: {successful} | ✗ Failed: {failed}")
                    
            except Exception as e: # Catch all exceptions during collection for a specific drug
                logger.error(f"Failed to collect {drug_name} due to unexpected error: {e}", exc_info=True)
                failed += 1
                
            # Rate limiting between drugs
            time.sleep(1) # Consider increasing if APIs are strict

        # Final summary
        logger.info("=" * 50)
        logger.info("COLLECTION COMPLETE")
        logger.info(f"Total drugs: {total}")
        logger.info(f"✓ Successful: {successful}")
        logger.info(f"✗ Failed: {failed}")
        if total > 0:
            logger.info(f"Success rate: {(successful/total)*100:.1f}%")
        else:
            logger.info("No drugs processed.")
        logger.info("=" * 50)


def main():
    """Main execution function"""
    logger.info("=" * 50)
    logger.info("PHARMACEUTICAL DATA COLLECTION PIPELINE")
    logger.info("=" * 50)
    
    # Check for OpenFDA API Key
    if OPENFDA_API_KEY == "YOUR_ACTUAL_OPENFDA_API_KEY":
        logger.error("ERROR: OpenFDA API Key not set. Please update OPENFDA_API_KEY in the script or set as an environment variable.")
        return
        
    # Initialize collector
    collector = DrugDataCollector()
    
    # Collect all drugs
    collector.collect_all_drugs(COMMON_DRUGS, batch_size=10)
    
    logger.info("Pipeline execution completed!")


if __name__ == "__main__":
    main()
    