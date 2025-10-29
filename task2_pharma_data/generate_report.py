import json
import re
from datetime import datetime
import sys

class ReportGenerator:
    """
    Generates a Markdown data quality report from a JSON results file
    and a Markdown template.
    """
    def __init__(self, json_path: str, template_path: str, output_path: str):
        self.json_path = json_path
        self.template_path = template_path
        self.output_path = output_path
        self.results = self._load_results()
        self.template_content = self._load_template()

    def _load_results(self) -> dict:
        """Loads the JSON results file."""
        try:
            with open(self.json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Error: JSON results file not found at '{self.json_path}'")
            print("Please run 'validate_data.py' first to generate the results.")
            sys.exit(1)
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON from '{self.json_path}'. The file may be empty or corrupted.")
            sys.exit(1)

    def _load_template(self) -> str:
        """Loads the Markdown template file."""
        try:
            with open(self.template_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            print(f"Error: Markdown template file not found at '{self.template_path}'")
            sys.exit(1)

    # --- THIS IS THE CORRECTED FUNCTION ---
    def _replace(self, placeholder: str, value: str, count: int = 1):
        """Helper function for safe replacement, with a count parameter."""
        # The str.replace method takes a 'count' argument. We pass it along.
        self.template_content = self.template_content.replace(placeholder, str(value), count)

    def _populate_summary(self):
        """Populates the Executive Summary section."""
        print("Populating Executive Summary...")
        
        # Date (replace only once)
        self._replace("[Date will be auto-filled when script runs]", datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC'))
        
        # Key Metrics
        total_drugs = self.results.get('total_drugs', 0)
        self._replace("[Auto-filled]", str(total_drugs))

        completeness_metrics = self.results.get('completeness_metrics', {})
        if completeness_metrics:
            overall_completeness = sum(m['percentage'] for m in completeness_metrics.values()) / len(completeness_metrics)
            self._replace("[Auto-filled]%", f"{overall_completeness:.1f}%")
        else:
            self._replace("[Auto-filled]%", "N/A")

        # Simple Data Quality Score Calculation
        score = 100
        for metrics in self.results.get('required_fields_check', {}).values():
            score -= (100 - metrics.get('percentage', 100)) * 0.5
        score -= len(self.results.get('consistency_issues', []))
        score -= len(self.results.get('duplicates', [])) * 2
        score = max(0, round(score))
        self._replace("[Auto-filled]/100", f"{int(score)}/100")
        
        # Status Overview
        req_fields_check = self.results.get('required_fields_check', {})
        avg_req_completeness = sum(m['percentage'] for m in req_fields_check.values()) / len(req_fields_check) if req_fields_check else 100
        self._replace("[X]% complete", f"{avg_req_completeness:.1f}%")
        self._replace("[X] found", str(len(self.results.get('consistency_issues', []))))
        self._replace("[X] found", str(len(self.results.get('duplicates', []))))
        standardization_count = self.results.get('medical_term_standardization', {}).get('drugs_needing_standardization', 0)
        self._replace("[X] drugs", f"{standardization_count} drugs")

    def _populate_table(self, section_header: str, rows: list):
        """Generic function to populate a markdown table."""
        # Using raw string (r"...") to avoid SyntaxWarning
        pattern = re.compile(r"(^{section_header}.*?^\|.*?\|.*?$[\r\n]+^\|:?--.*?)(\n.*?)?(?=\n\n##|\Z)".format(section_header=re.escape(section_header)), re.MULTILINE | re.DOTALL)
        match = pattern.search(self.template_content)

        if match:
            header_part = match.group(1)
            # Find the start of the old table body to replace it
            table_start_index = match.start()
            new_table_content = header_part + "\n" + "\n".join(rows)
            
            # Replace the entire old table block with the new one
            self.template_content = self.template_content[:table_start_index] + new_table_content + self.template_content[match.end():]
        else:
            print(f"Warning: Could not find table placeholder for section '{section_header}'")

    def _populate_required_fields(self):
        """Populates the Required Fields Validation section."""
        print("Populating Required Fields section...")
        table_rows = [f"| {field} | {metrics['present']} | {metrics['missing']} | {metrics['percentage']:.1f}% |"
                      for field, metrics in self.results.get('required_fields_check', {}).items()]
        self._populate_table("### Results", table_rows)
        
        missing_drugs_text = [f"- **{field}:** {', '.join(metrics['missing_drugs'])}"
                              for field, metrics in self.results.get('required_fields_check', {}).items() if metrics['missing'] > 0]
        self._replace("[Auto-filled list of drugs]", "\n".join(missing_drugs_text) or "None")
        
        issues_found_text = [f"- '{field}' is missing in {metrics['missing']} records, impacting core functionality."
                             for field, metrics in self.results.get('required_fields_check', {}).items() if metrics['missing'] > 0]
        self._replace("[List of specific issues will be auto-filled]", "\n".join(issues_found_text) or "No critical issues found.")

    def _populate_completeness(self):
        """Populates the Data Completeness Analysis section."""
        print("Populating Completeness section...")
        completeness_metrics = self.results.get('completeness_metrics', {})
        
        table_rows = [f"| {field} | {metrics['populated']} | {metrics['total']} | {metrics['percentage']:.1f}% |"
                      for field, metrics in completeness_metrics.items()]
        self._populate_table("### Overall Field Completeness", table_rows)

        high = [f for f, m in completeness_metrics.items() if m.get('percentage', 0) > 90]
        medium = [f for f, m in completeness_metrics.items() if 70 <= m.get('percentage', 0) <= 90]
        low = [f for f, m in completeness_metrics.items() if m.get('percentage', 0) < 70]
        self._replace("- [Auto-filled]", "- " + (", ".join(high) or "None"))
        self._replace("- [Auto-filled]", "- " + (", ".join(medium) or "None"))
        self._replace("- [Auto-filled]", "- " + (", ".join(low) or "None"))

        targets = {'drug_name': 100, 'generic_name': 100, 'indications': 100, 'dosage_forms': 90,
                   'side_effects': 90, 'mechanism_of_action': 80, 'contraindications': 80, 'drug_interactions': 70}
        perf_rows = []
        for field, target_perc in targets.items():
            actual_perc = completeness_metrics.get(field, {}).get('percentage', 0)
            status = "✅" if actual_perc >= target_perc else ("⚠️" if actual_perc >= target_perc * 0.8 else "❌")
            perf_rows.append(f"| {field} | {target_perc}% | {actual_perc:.1f}% | {status} |")
        self._populate_table("### Target vs. Actual Performance", perf_rows)

    def generate_report(self):
        """Generates the final Markdown report."""
        self._populate_summary()
        self._populate_required_fields()
        self._populate_completeness()
        # You can add calls to populate other sections here
        
        # Simple replacements for remaining items
        self._replace("[X] drugs with invalid dosage formats", str(self.results.get('format_validation', {}).get('dosage_format_issues', 'N/A')))
        self._replace("[X] drugs with invalid date formats", str(self.results.get('format_validation', {}).get('invalid_dates_count', 'N/A')))
        
        try:
            with open(self.output_path, 'w', encoding='utf-8') as f:
                f.write(self.template_content)
            print(f"\nReport successfully generated at: {self.output_path}")
        except IOError as e:
            print(f"Error writing report to file: {e}")

def main():
    """Main execution function."""
    print("=" * 50)
    print("Generating Data Quality Report...")
    print("=" * 50)
    
    generator = ReportGenerator(
        json_path="data_quality_report.json",
        template_path="data_quality_report.md",
        output_path="Generated_Data_Quality_Report.md"
    )
    generator.generate_report()

if __name__ == "__main__":
    main()