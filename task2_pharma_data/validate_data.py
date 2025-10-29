"""
Data Quality and Validation Script
Validates pharmaceutical data collected in drugs.db
"""

import sqlite3
import json
import re
from typing import Dict, List, Tuple
from datetime import datetime
import logging

# Setup logging
import sys
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/validation.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')


class DrugDataValidator:
    """Validates pharmaceutical data quality"""
    
    def __init__(self, db_path: str = "data/drugs.db"):
        self.db_path = db_path
        self.validation_results = {
            'total_drugs': 0,
            'required_fields_check': {},
            'format_validation': {},
            'completeness_metrics': {},
            'consistency_issues': [],
            'duplicates': [],
            'medical_term_standardization': {},
            'recommendations': []
        }
        
        # Required fields for each drug
        self.required_fields = ['drug_name', 'indications', 'side_effects']
        
        # Medical terminology mappings for standardization
        self.medical_term_mappings = {
            'high blood pressure': 'hypertension',
            'elevated blood pressure': 'hypertension',
            'high bp': 'hypertension',
            'diabetes mellitus': 'diabetes',
            'sugar disease': 'diabetes',
            'heart attack': 'myocardial infarction',
            'stroke': 'cerebrovascular accident',
            'chest pain': 'angina',
            'difficulty breathing': 'dyspnea',
            'shortness of breath': 'dyspnea'
        }
    
    def connect_db(self) -> sqlite3.Connection:
        """Create database connection"""
        return sqlite3.connect(self.db_path)
    
    def get_all_drugs(self) -> List[Dict]:
        """Fetch all drugs from database"""
        conn = self.connect_db()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM drugs")
        columns = [description[0] for description in cursor.description]
        
        drugs = []
        for row in cursor.fetchall():
            drug = dict(zip(columns, row))
            
            # Parse JSON fields
            json_fields = ['brand_names', 'indications', 'mechanism_of_action', 
                          'dosage_forms', 'common_dosages', 'side_effects',
                          'contraindications', 'drug_interactions', 'data_sources']
            
            for field in json_fields:
                if drug.get(field):
                    try:
                        drug[field] = json.loads(drug[field])
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse JSON for {drug['drug_name']}.{field}")
                        drug[field] = []
            
            drugs.append(drug)
        
        conn.close()
        self.validation_results['total_drugs'] = len(drugs)
        logger.info(f"Loaded {len(drugs)} drugs from database")
        return drugs
    
    def validate_required_fields(self, drugs: List[Dict]) -> Dict:
        """
        Check if all required fields are present and not empty
        
        Returns:
            Dictionary with validation results
        """
        logger.info("Validating required fields...")
        
        missing_fields = {field: [] for field in self.required_fields}
        
        for drug in drugs:
            for field in self.required_fields:
                value = drug.get(field)
                
                # Check if field is missing or empty
                if not value:
                    missing_fields[field].append(drug['drug_name'])
                elif isinstance(value, (list, dict)):
                    if len(value) == 0:
                        missing_fields[field].append(drug['drug_name'])
        
        results = {}
        for field in self.required_fields:
            missing_count = len(missing_fields[field])
            total = len(drugs)
            present_percentage = ((total - missing_count) / total * 100) if total > 0 else 0
            
            results[field] = {
                'present': total - missing_count,
                'missing': missing_count,
                'percentage': round(present_percentage, 2),
                'missing_drugs': missing_fields[field][:10]  # First 10 examples
            }
            
            logger.info(f"✓ {field}: {present_percentage:.1f}% complete")
        
        self.validation_results['required_fields_check'] = results
        return results
    
    def validate_format(self, drugs: List[Dict]) -> Dict:
        """
        Validate data format consistency
        
        Returns:
            Dictionary with format validation results
        """
        logger.info("Validating data formats...")
        
        format_issues = {
            'dosage_format': [],
            'invalid_dates': [],
            'empty_lists_as_strings': []
        }
        
        # Dosage format regex: matches patterns like "500mg", "1g", "10mcg"
        dosage_pattern = re.compile(r'^\d+(\.\d+)?\s*(mg|mcg|g|ml|units?)$', re.IGNORECASE)
        
        for drug in drugs:
            drug_name = drug['drug_name']
            
            # Check dosage formats
            dosages = drug.get('common_dosages', [])
            if isinstance(dosages, list):
                for dosage in dosages:
                    if isinstance(dosage, str) and not dosage_pattern.match(dosage.strip()):
                        format_issues['dosage_format'].append({
                            'drug': drug_name,
                            'invalid_dosage': dosage
                        })
            
            # Check date format
            last_updated = drug.get('last_updated')
            if last_updated:
                try:
                    datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    format_issues['invalid_dates'].append(drug_name)
        
        results = {
            'dosage_format_issues': len(format_issues['dosage_format']),
            'invalid_dates_count': len(format_issues['invalid_dates']),
            'examples': {
                'dosage_issues': format_issues['dosage_format'][:5],
                'date_issues': format_issues['invalid_dates'][:5]
            }
        }
        
        self.validation_results['format_validation'] = results
        logger.info(f"✓ Found {len(format_issues['dosage_format'])} dosage format issues")
        return results
    
    def calculate_completeness_metrics(self, drugs: List[Dict]) -> Dict:
        """
        Calculate completeness percentage for all fields
        
        Returns:
            Dictionary with completeness metrics
        """
        logger.info("Calculating completeness metrics...")
        
        all_fields = ['drug_name', 'generic_name', 'brand_names', 'drug_class',
                     'indications', 'mechanism_of_action', 'dosage_forms',
                     'common_dosages', 'side_effects', 'contraindications',
                     'drug_interactions', 'data_sources']
        
        completeness = {}
        
        for field in all_fields:
            populated = 0
            for drug in drugs:
                value = drug.get(field)
                
                if value:
                    if isinstance(value, str) and value.strip():
                        populated += 1
                    elif isinstance(value, list) and len(value) > 0:
                        populated += 1
                    elif isinstance(value, dict) and any(value.values()):
                        populated += 1
            
            total = len(drugs)
            percentage = (populated / total * 100) if total > 0 else 0
            
            completeness[field] = {
                'populated': populated,
                'total': total,
                'percentage': round(percentage, 2)
            }
        
        self.validation_results['completeness_metrics'] = completeness
        
        # Log summary
        logger.info("Completeness Summary:")
        for field, metrics in completeness.items():
            logger.info(f"  {field}: {metrics['percentage']:.1f}%")
        
        return completeness
    
    def check_cross_source_consistency(self, drugs: List[Dict]) -> List[Dict]:
        """
        Check for consistency issues across data sources
        
        Returns:
            List of consistency issues found
        """
        logger.info("Checking cross-source consistency...")
        
        issues = []
        
        for drug in drugs:
            drug_name = drug['drug_name']
            sources = drug.get('data_sources', [])
            
            # If multiple sources, check for potential conflicts
            if len(sources) > 1:
                # Check if indications are too few despite multiple sources
                indications = drug.get('indications', [])
                if len(indications) < 1:
                    issues.append({
                        'drug': drug_name,
                        'issue': 'Multiple sources but no indications',
                        'sources': sources
                    })
                
                # Check if side effects are missing
                side_effects = drug.get('side_effects', {})
                if isinstance(side_effects, dict):
                    common = side_effects.get('common', [])
                    serious = side_effects.get('serious', [])
                    if len(common) == 0 and len(serious) == 0:
                        issues.append({
                            'drug': drug_name,
                            'issue': 'Multiple sources but no side effects',
                            'sources': sources
                        })
        
        self.validation_results['consistency_issues'] = issues[:20]  # First 20 examples
        logger.info(f"✓ Found {len(issues)} consistency issues")
        return issues
    
    def detect_duplicates(self, drugs: List[Dict]) -> List[Dict]:
        """
        Detect potential duplicate entries
        
        Returns:
            List of potential duplicates
        """
        logger.info("Detecting duplicate entries...")
        
        duplicates = []
        seen_names = {}
        
        for drug in drugs:
            drug_name = drug['drug_name'].lower().strip()
            generic_name = drug.get('generic_name', '').lower().strip()
            
            # Check for duplicate drug names
            if drug_name in seen_names:
                duplicates.append({
                    'drug_1': seen_names[drug_name],
                    'drug_2': drug['drug_name'],
                    'type': 'exact_name_match'
                })
            else:
                seen_names[drug_name] = drug['drug_name']
            
            # Check for generic name matching another drug's brand name
            if generic_name:
                if generic_name in seen_names and generic_name != drug_name:
                    duplicates.append({
                        'drug_1': seen_names[generic_name],
                        'drug_2': drug['drug_name'],
                        'type': 'generic_brand_overlap'
                    })
        
        self.validation_results['duplicates'] = duplicates
        logger.info(f"✓ Found {len(duplicates)} potential duplicates")
        return duplicates
    
    def standardize_medical_terms(self, drugs: List[Dict]) -> Dict:
        """
        Check for medical terminology that should be standardized
        
        Returns:
            Dictionary with standardization suggestions
        """
        logger.info("Checking medical terminology standardization...")
        
        suggestions = {}
        
        for drug in drugs:
            drug_name = drug['drug_name']
            
            # Check indications
            indications = drug.get('indications', [])
            for indication in indications:
                if isinstance(indication, str):
                    indication_lower = indication.lower()
                    for informal_term, standard_term in self.medical_term_mappings.items():
                        if informal_term in indication_lower:
                            if drug_name not in suggestions:
                                suggestions[drug_name] = []
                            suggestions[drug_name].append({
                                'field': 'indications',
                                'found': informal_term,
                                'suggested': standard_term,
                                'original_text': indication
                            })
        
        self.validation_results['medical_term_standardization'] = {
            'drugs_needing_standardization': len(suggestions),
            'examples': dict(list(suggestions.items())[:10])  # First 10 examples
        }
        
        logger.info(f"✓ Found {len(suggestions)} drugs with non-standard terminology")
        return suggestions
    
    def generate_recommendations(self):
        """Generate recommendations based on validation results"""
        logger.info("Generating recommendations...")
        
        recommendations = []
        
        # Required fields recommendations
        required = self.validation_results.get('required_fields_check', {})
        for field, metrics in required.items():
            if metrics['percentage'] < 100:
                recommendations.append({
                    'priority': 'HIGH' if metrics['percentage'] < 80 else 'MEDIUM',
                    'category': 'Completeness',
                    'issue': f"{field} missing in {metrics['missing']} drugs ({100-metrics['percentage']:.1f}%)",
                    'action': f"Re-collect data for drugs: {', '.join(metrics['missing_drugs'][:5])}"
                })
        
        # Completeness recommendations
        completeness = self.validation_results.get('completeness_metrics', {})
        for field, metrics in completeness.items():
            if metrics['percentage'] < 70:
                recommendations.append({
                    'priority': 'MEDIUM',
                    'category': 'Data Enrichment',
                    'issue': f"{field} only {metrics['percentage']:.1f}% complete",
                    'action': f"Consider additional data sources for {field}"
                })
        
        # Consistency issues
        consistency_issues = self.validation_results.get('consistency_issues', [])
        if len(consistency_issues) > 10:
            recommendations.append({
                'priority': 'HIGH',
                'category': 'Data Quality',
                'issue': f"{len(consistency_issues)} drugs have consistency issues across sources",
                'action': "Manual review recommended for drugs with multiple sources but missing critical data"
            })
        
        # Duplicates
        duplicates = self.validation_results.get('duplicates', [])
        if len(duplicates) > 0:
            recommendations.append({
                'priority': 'HIGH',
                'category': 'Data Integrity',
                'issue': f"{len(duplicates)} potential duplicate entries found",
                'action': "Review and merge or remove duplicate entries"
            })
        
        # Medical terminology
        standardization = self.validation_results.get('medical_term_standardization', {})
        if standardization.get('drugs_needing_standardization', 0) > 5:
            recommendations.append({
                'priority': 'LOW',
                'category': 'Standardization',
                'issue': f"{standardization['drugs_needing_standardization']} drugs use non-standard medical terms",
                'action': "Implement automated term standardization pipeline"
            })
        
        self.validation_results['recommendations'] = recommendations
        
        # Log recommendations
        logger.info("\n" + "=" * 60)
        logger.info("RECOMMENDATIONS:")
        for i, rec in enumerate(recommendations, 1):
            logger.info(f"{i}. [{rec['priority']}] {rec['issue']}")
            logger.info(f"   → {rec['action']}")
        logger.info("=" * 60)
        
        return recommendations
    
    def run_full_validation(self) -> Dict:
        """
        Run all validation checks
        
        Returns:
            Complete validation results
        """
        logger.info("=" * 60)
        logger.info("STARTING FULL DATA VALIDATION")
        logger.info("=" * 60)
        
        # Load data
        drugs = self.get_all_drugs()
        
        if len(drugs) == 0:
            logger.error("No drugs found in database!")
            return self.validation_results
        
        # Run all validation checks
        self.validate_required_fields(drugs)
        self.validate_format(drugs)
        self.calculate_completeness_metrics(drugs)
        self.check_cross_source_consistency(drugs)
        self.detect_duplicates(drugs)
        self.standardize_medical_terms(drugs)
        self.generate_recommendations()
        
        logger.info("=" * 60)
        logger.info("VALIDATION COMPLETE")
        logger.info("=" * 60)
        
        return self.validation_results
    
    def save_results_to_file(self, output_path: str = "data_quality_report.json"):
        """Save validation results to JSON file"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.validation_results, f, indent=2, ensure_ascii=False)
        logger.info(f"✓ Results saved to {output_path}")


def main():
    """Main execution function"""
    validator = DrugDataValidator()
    
    # Run validation
    results = validator.run_full_validation()
    
    # Save results
    validator.save_results_to_file()
    
    # Print summary
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    print(f"Total Drugs Validated: {results['total_drugs']}")
    print(f"\nRequired Fields Check:")
    for field, metrics in results.get('required_fields_check', {}).items():
        print(f"  {field}: {metrics['percentage']:.1f}% complete")
    
    print(f"\nConsistency Issues: {len(results.get('consistency_issues', []))}")
    print(f"Duplicate Entries: {len(results.get('duplicates', []))}")
    print(f"Recommendations: {len(results.get('recommendations', []))}")
    print("=" * 60)


if __name__ == "__main__":
    main()