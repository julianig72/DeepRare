import os
import yaml
import subprocess
import json
from pathlib import Path

class ExomiserAnalyzer:
    def __init__(self, exomiser_jar_path, output_dir="./exomiser_results"):
        """
        Initialize Exomiser analyzer
        
        Args:
            exomiser_jar_path: Path to exomiser JAR file
            output_dir: Directory to save results
        """
        self.exomiser_jar = exomiser_jar_path
        self.output_dir = output_dir
        
        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Template configuration
        self.config_template = {
            "analysis": {
                "genomeAssembly": "GRCh37",
                "outputOptions": {
                    "outputFormat": ["TSV", "HTML"],
                },
                "frequencySources": [
                    "THOUSAND_GENOMES", "TOPMED", "UK10K", "ESP_AA", "ESP_EA", "ESP_ALL",
                    "GNOMAD_E_AFR", "GNOMAD_E_AMR", "GNOMAD_E_EAS", "GNOMAD_E_NFE", "GNOMAD_E_SAS",
                    "GNOMAD_G_AFR", "GNOMAD_G_AMR", "GNOMAD_G_EAS", "GNOMAD_G_NFE", "GNOMAD_G_SAS"
                ],
                "pathogenicitySources": ["POLYPHEN", "MUTATION_TASTER", "SIFT"],
                "analysisMode": "PASS_ONLY",
                "inheritanceModes": {
                    "AUTOSOMAL_DOMINANT": 0.1,
                    "AUTOSOMAL_RECESSIVE_HOM_ALT": 0.1,
                    "AUTOSOMAL_RECESSIVE_COMP_HET": 2.0,
                    "X_DOMINANT": 0.1,
                    "X_RECESSIVE_HOM_ALT": 0.1,
                    "X_RECESSIVE_COMP_HET": 2.0,
                    "MITOCHONDRIAL": 0.2
                },
                "steps": [
                    {"failedVariantFilter": {}},
                    {"variantEffectFilter": {
                        "remove": [
                            "FIVE_PRIME_UTR_EXON_VARIANT", "FIVE_PRIME_UTR_INTRON_VARIANT",
                            "THREE_PRIME_UTR_EXON_VARIANT", "THREE_PRIME_UTR_INTRON_VARIANT",
                            "NON_CODING_TRANSCRIPT_EXON_VARIANT", "NON_CODING_TRANSCRIPT_INTRON_VARIANT",
                            "CODING_TRANSCRIPT_INTRON_VARIANT", "UPSTREAM_GENE_VARIANT",
                            "DOWNSTREAM_GENE_VARIANT", "INTERGENIC_VARIANT", "REGULATORY_REGION_VARIANT"
                        ]
                    }},
                    {"frequencyFilter": {"maxFrequency": 1.0}},
                    {"pathogenicityFilter": {"keepNonPathogenic": True}},
                    {"inheritanceFilter": {}},
                    {"omimPrioritiser": {}},
                    {"hiPhivePrioritiser": {}}
                ]
            }
        }

    def create_config(self, vcf_path, hpo_ids, sample_id):
        """
        Create Exomiser configuration for a single sample
        
        Args:
            vcf_path: Path to VCF file
            hpo_ids: List of HPO IDs
            sample_id: Sample identifier
            
        Returns:
            Path to created config file
        """
        # Create config from template
        config = self.config_template.copy()
        config['analysis']['vcf'] = str(vcf_path)
        config['analysis']['hpoIds'] = hpo_ids
        
        # Set output prefix
        output_prefix = os.path.join(self.output_dir, f"{sample_id}.phenix")
        config['analysis']['outputOptions']['outputPrefix'] = output_prefix
        
        # Save config file
        config_path = os.path.join(self.output_dir, f"{sample_id}.exomiser.yml")
        with open(config_path, 'w') as f:
            yaml.dump(config, f, sort_keys=False)
        
        return config_path

    def _get_result_paths(self, sample_id):
        """Get expected result file paths"""
        base_path = os.path.join(self.output_dir, f"{sample_id}.phenix")
        return {
            'html': f"{base_path}.html",
            'tsv': f"{base_path}.tsv",
            'config': os.path.join(self.output_dir, f"{sample_id}.exomiser.yml"),
            'json': os.path.join(self.output_dir, f"{sample_id}.flt-exomiser.json")
        }

    def _run_exomiser(self, config_path):
        """Execute Exomiser with the given config"""
        cmd = [
            'java',
            '-Xms4g',
            '-Xmx8g',
            '-jar', self.exomiser_jar,
            '--analysis', config_path
        ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            print("Exomiser completed successfully")
        except subprocess.CalledProcessError as e:
            print(f"Exomiser failed with error: {e}")
            print(f"stdout: {e.stdout}")
            print(f"stderr: {e.stderr}")
            raise

    def run_analysis(self, vcf_path, hpo_ids, sample_id=None, force=False):
        """
        Run Exomiser analysis for a single sample
        
        Args:
            vcf_path: Path to VCF file
            hpo_ids: List of HPO IDs (e.g., ['HP:0000252', 'HP:0001250'])
            sample_id: Sample identifier (if None, derived from VCF filename)
            force: If True, overwrite existing results
            
        Returns:
            Dictionary with analysis results and metadata
        """
        # Validate inputs
        if not os.path.exists(vcf_path):
            raise FileNotFoundError(f"VCF file not found: {vcf_path}")
        
        if not isinstance(hpo_ids, list) or len(hpo_ids) == 0:
            raise ValueError("hpo_ids must be a non-empty list")
        
        # Generate sample ID if not provided
        if sample_id is None:
            sample_id = Path(vcf_path).stem
            # Remove .vcf extension if present
            if sample_id.endswith('.vcf'):
                sample_id = sample_id[:-4]
        
        # Check if results already exist
        result_files = self._get_result_paths(sample_id)
        if not force and all(os.path.exists(path) for path in [result_files['html'], result_files['tsv']]):
            print(f"Results already exist for {sample_id}. Use force=True to overwrite.")
        else:
            # Create configuration
            print(f"Creating configuration for sample: {sample_id}")
            config_path = self.create_config(vcf_path, hpo_ids, sample_id)
            
            # Run Exomiser
            print(f"Running Exomiser analysis...")
            self._run_exomiser(config_path)
            
            print(f"Analysis completed for {sample_id}")
        
        # Return analysis results with metadata
        return {
            "sample_id": sample_id,
            "vcf_path": vcf_path,
            "hpo_ids": hpo_ids,
            "result_files": result_files,
            "output_dir": self.output_dir
        }

    def read_exomiser_summary(self, exomiser_json_path, max_genes=5):
        """
        Summarize top Exomiser candidate genes/variants and associated diseases.

        :param exomiser_json_path: Path to Exomiser JSON result.
        :param max_genes: Number of top genes to summarize.
        :return: Multi-line string summary.
        """
        with open(exomiser_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        summary_lines = []
        for entry in data[:max_genes]:
            gene = entry.get("gene", "N/A")
            url = entry.get("gene_url", "")
            exomiser_score = entry.get("exomiser_score", "N/A")
            phenotype_score = entry.get("phenotype_score", "N/A")
            variant_score = entry.get("variant_score", "N/A")
            variant_info = entry.get("variant_info", "N/A")
            acmg = entry.get("acmg", "N/A")
            clinvar = entry.get("clinvar", "N/A")
            diseases = entry.get("diseases", [])

            summary_lines.append(
                f"Gene: {gene} ({url})\n"
                f"  Exomiser score: {exomiser_score}, Phenotype score: {phenotype_score}, Variant score: {variant_score}\n"
                f"  Variant: {variant_info.strip()} | ACMG: {acmg} | ClinVar: {clinvar}"
            )
            if diseases:
                summary_lines.append("  Associated diseases:")
                for dis in diseases:
                    summary_lines.append(f"    - {dis['name']} ({dis['link']})")
            else:
                summary_lines.append("  Associated diseases: None")
            summary_lines.append("")  # Blank line between genes

        return "\n".join(summary_lines).strip()


class DiagnosisInference:
    def __init__(self, output_dir="./exomiser_results"):
        """
        Initialize diagnosis inference
        
        Args:
            output_dir: Directory to save results (should match ExomiserAnalyzer output_dir)
        """
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def build_diagnosis_prompt(self, exomiser_summary, hpo_terms, pheno_only_diagnosis):
        """
        Build prompt for disease diagnosis based on Exomiser results
        
        Args:
            exomiser_summary: Summary from Exomiser results
            hpo_terms: HPO terms description
            pheno_only_diagnosis: Preliminary diagnosis based on phenotype
            
        Returns:
            Formatted prompt string
        """
        prompt = (
            "Here is a rare disease diagnosis case.\n\n"
            "Exomiser gene/variant prioritization summary:\n"
            f"{exomiser_summary}\n\n"
            f"Phenotypic description (HPO terms): {hpo_terms}\n\n"
            f"Preliminary diagnosis based only on phenotype: {pheno_only_diagnosis}\n\n"
            "Based on the Exomiser summary, phenotype, and preliminary diagnosis, enumerate the top 5 most likely rare disease diagnoses. "
            "Use ** to tag each disease name. "
            "Please consider more on gene results from Exomiser, and the phenotype and preliminary diagnosis are only for reference. "
        )
        return prompt

    def run_inference(self, exomiser_analysis_result, patient_info="", 
                     preliminary_diagnosis="", api_interface=None, 
                     model="deepseek-v3-241226",
                     system_prompt="You are an expert in rare disease diagnosis.",
                     force=False, max_genes=5):
        """
        Run disease diagnosis inference based on Exomiser analysis results
        
        Args:
            exomiser_analysis_result: Output from ExomiserAnalyzer.run_analysis()
            patient_info: Patient phenotype information
            preliminary_diagnosis: Preliminary diagnosis based on phenotype
            api_interface: API interface object (should have get_completion method)
            model: Model name for API
            system_prompt: System prompt for API
            force: Force re-run if results exist
            max_genes: Number of top genes to include in summary
            
        Returns:
            Dictionary with complete diagnosis results
        """
        sample_id = exomiser_analysis_result["sample_id"]
        hpo_ids = exomiser_analysis_result["hpo_ids"]
        result_files = exomiser_analysis_result["result_files"]
        
        # Check if diagnosis result already exists
        diagnosis_result_path = os.path.join(self.output_dir, f"diagnosis_result_{sample_id}.json")
        if not force and os.path.exists(diagnosis_result_path):
            print(f"Diagnosis result already exists for {sample_id}. Use force=True to overwrite.")
            with open(diagnosis_result_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        try:
            # Step 1: Generate Exomiser summary
            exomiser_json_path = result_files.get('json')
            if not exomiser_json_path or not os.path.exists(exomiser_json_path):
                print(f"Warning: Exomiser JSON result not found at {exomiser_json_path}")
                print("You may need to post-process the TSV results to generate the JSON file")
                exomiser_summary = "Exomiser JSON results not available"
            else:
                print(f"Generating Exomiser summary for {sample_id}")
                # Create a temporary analyzer instance to use the summary method
                temp_analyzer = ExomiserAnalyzer("", self.output_dir)
                exomiser_summary = temp_analyzer.read_exomiser_summary(exomiser_json_path, max_genes)
            
            # Step 2: Build diagnosis prompt
            user_prompt = self.build_diagnosis_prompt(
                exomiser_summary, 
                patient_info or str(hpo_ids), 
                preliminary_diagnosis
            )
            
            # Step 3: Get diagnosis if API interface is provided
            ai_diagnosis = ""
            if api_interface:
                print(f"Running AI diagnosis inference for {sample_id}")
                try:
                    ai_diagnosis = api_interface.get_completion(system_prompt, user_prompt)
                except Exception as e:
                    print(f"API call failed: {e}")
                    ai_diagnosis = "API call failed"
            else:
                print("No API interface provided, skipping AI diagnosis")
            
            # Step 4: Compile results
            final_result = {
                "sample_id": sample_id,
                "vcf_path": exomiser_analysis_result["vcf_path"],
                "hpo_ids": hpo_ids,
                "patient_info": patient_info,
                "preliminary_diagnosis": preliminary_diagnosis,
                "exomiser_analysis_result": exomiser_analysis_result,
                "exomiser_summary": exomiser_summary,
                "diagnosis_prompt": user_prompt,
                "ai_diagnosis": ai_diagnosis,
                "model_used": model,
                "max_genes": max_genes
            }
            
            # Step 5: Save results
            with open(diagnosis_result_path, 'w', encoding='utf-8') as f:
                json.dump(final_result, f, ensure_ascii=False, indent=4)
            
            print(f"Complete diagnosis analysis saved to {diagnosis_result_path}")
            return final_result
            
        except Exception as e:
            print(f"Error in diagnosis inference for {sample_id}: {e}")
            raise



if __name__ == "__main__":

    exomiser_analyzer = ExomiserAnalyzer("/path/to/exomiser.jar", "./results")
    exomiser_result = exomiser_analyzer.run_analysis(
        vcf_path="/path/to/sample.vcf",
        hpo_ids=["HP:0000252", "HP:0001250"]
    )

    diagnosis_inference = DiagnosisInference("./results")
    diagnosis_result = diagnosis_inference.run_inference(
        exomiser_analysis_result=exomiser_result,
        patient_info="Patient has microcephaly and seizures",
        preliminary_diagnosis="Neurodevelopmental disorder",
        api_interface=None, 
        force=False
    )