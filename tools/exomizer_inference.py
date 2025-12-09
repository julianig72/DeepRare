import os
import yaml
import subprocess
import json
from pathlib import Path
from bs4 import BeautifulSoup

def extract_gene_panels(html_file):
    with open(html_file, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')

    panels = []
    for div in soup.find_all('div', class_='panel panel-default'):
        heading = div.find('div', class_='panel-heading')
        if not heading:
            continue
        gene_link = heading.find('a', href=True)
        if not gene_link:
            continue

        gene_name = gene_link.text.strip()
        gene_url = gene_link['href']
        exomiser_score = None
        phenotype_score = None
        variant_score = None
        p_value = None
        for h4 in heading.find_all('h4'):
            text = h4.get_text(" ", strip=True)
            if 'Exomiser Score:' in text:
                parts = text.split()
                for i, part in enumerate(parts):
                    if part == 'Score:':
                        try:
                            exomiser_score = float(parts[i+1])
                        except Exception:
                            pass
                if '(' in text and 'p=' in text:
                    p_value = text.split('p=')[1].split(')')[0]
            elif 'Phenotype Score:' in text:
                try:
                    phenotype_score = float(text.split(':')[-1])
                except Exception:
                    pass
            elif 'Variant Score:' in text:
                try:
                    variant_score = float(text.split(':')[-1])
                except Exception:
                    pass

        variant_info = ''
        acmg = ''
        clinvar = ''
        panel_body = div.find('div', class_='panel-body')
        if panel_body:
            label = panel_body.find('span', class_='label label-danger')
            if label:
                variant_type = label.text.strip()
                descr = label.find_next_sibling(text=True)
                if descr:
                    variant_info = variant_type + ' ' + descr.strip()
            # ACMG
            acmg_label = panel_body.find('span', class_='label label-danger')
            if not acmg_label:
                acmg_label = panel_body.find('span', class_='label label-default')
            if not acmg_label:
                acmg_label = panel_body.find('span', class_='label label-warning')
            if not acmg_label:
                acmg_label = panel_body.find('span', class_='label label-info')
            if acmg_label:
                acmg = acmg_label.text.strip()
            # ClinVar
            clinvar_label = panel_body.find('span', class_='label label-success')
            if not clinvar_label:
                clinvar_label = panel_body.find('span', class_='label label-default')
            if not clinvar_label:
                clinvar_label = panel_body.find('span', class_='label label-danger')
            if clinvar_label:
                clinvar = clinvar_label.text.strip()

        diseases = []
        if panel_body:
            for dt in panel_body.find_all('dt'):
                if 'Known diseases' in dt.get_text():
                    dd = dt.find_next_siblings('dd')
                    for d in dd:
                        a = d.find('a', href=True)
                        if a:
                            diseases.append({
                                'name': a.text.strip() + ' ' + d.text.replace(a.text, '').strip(),
                                'link': a['href']
                            })

        panels.append({
            'gene': gene_name,
            'gene_url': gene_url,
            'exomiser_score': exomiser_score,
            'phenotype_score': phenotype_score,
            'variant_score': variant_score,
            'p_value': p_value,
            'variant_info': variant_info,
            'acmg': acmg,
            'clinvar': clinvar,
            'diseases': diseases
        })

    panels = [p for p in panels if p['exomiser_score'] is not None]
    panels.sort(key=lambda x: x['exomiser_score'], reverse=True)
    return panels[:20]


class ExomiserRunner:
    def __init__(self, exomiser_jar_path, output_dir="exomiser_results"):
        """
        Initialize Exomiser runner
        
        Args:
            exomiser_jar_path: Path to exomiser JAR file
            output_dir: Directory to save results
        """
        self.exomiser_jar = exomiser_jar_path
        BASE_PATH = os.path.dirname(os.path.abspath(__file__))
        PARENT_PATH = os.path.dirname(BASE_PATH)
        self.output_dir = os.path.join(PARENT_PATH, output_dir)
        
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

    def run_analysis(self, vcf_path, hpo_ids, sample_id=None, force=False, output_dir=None):
        """
        Run Exomiser analysis for a single sample
        
        Args:
            vcf_path: Path to VCF file
            hpo_ids: List of HPO IDs (e.g., ['HP:0000252', 'HP:0001250'])
            sample_id: Sample identifier (if None, derived from VCF filename)
            force: If True, overwrite existing results
            
        Returns:
            Dictionary with result file paths
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
        if not force and all(os.path.exists(path) for path in result_files.values()):
            print(f"Results already exist for {sample_id}. Use force=True to overwrite.")
            return result_files
        
        # Create configuration
        print(f"Creating configuration for sample: {sample_id}")
        config_path = self.create_config(vcf_path, hpo_ids, sample_id)
        
        # Run Exomiser
        print(f"Running Exomiser analysis...")
        self._run_exomiser(config_path, output_dir)
        
        print(f"Analysis completed for {sample_id}")
        return result_files

    def _get_result_paths(self, sample_id):
        """Get expected result file paths"""
        base_path = os.path.join(self.output_dir, f"{sample_id}")
        return {
            'html': f"{base_path}.html",
            'tsv': f"{base_path}.tsv",
            'config': os.path.join(self.output_dir, f"{sample_id}.exomiser.yml")
        }

    def _run_exomiser(self, config_path, output_dir):
        """Execute Exomiser with the given config"""
         # Make sure output directory exists
        output_dir = os.path.abspath(output_dir)
        os.makedirs(output_dir, exist_ok=True)
        
        output_filename = os.path.basename(config_path).replace('.exomiser.yml', '')

        cmd = [
            'java',
            '-Xms4g',
            '-Xmx8g',
            f'-Dspring.config.location=file:{os.path.dirname(self.exomiser_jar)}/application.properties',
            '-jar', self.exomiser_jar,
            '--analysis', config_path,
            '--output-directory', output_dir,      
            '--output-filename', output_filename,     
            '--output-format', 'HTML' 
        ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            print("Exomiser completed successfully")
        except subprocess.CalledProcessError as e:
            print(f"Exomiser failed with error: {e}")
            print(f"stdout: {e.stdout}")
            print(f"stderr: {e.stderr}")
            raise

    def read_exomiser_summary(self, data, max_genes=5):
        """
        Summarize top Exomiser candidate genes/variants and associated diseases.

        :param exomiser_json_path: Path to Exomiser JSON result.
        :param max_genes: Number of top genes to summarize.
        :return: Multi-line string summary.
        """
        # with open(exomiser_json_path, "r", encoding="utf-8") as f:
        #     data = json.load(f)
        
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

    def run_diagnosis_inference(self, vcf_path, hpo_ids, patient_info="", 
                              preliminary_diagnosis="", sample_id=None, 
                              api_interface=None, model="deepseek-v3-241226",
                              system_prompt="You are an expert in rare disease diagnosis.",
                              force=False):
        """
        Run complete pipeline: Exomiser analysis + disease diagnosis inference
        
        Args:
            vcf_path: Path to VCF file
            hpo_ids: List of HPO IDs
            patient_info: Patient phenotype information
            preliminary_diagnosis: Preliminary diagnosis based on phenotype
            sample_id: Sample identifier
            api_interface: API interface object (should have get_completion method)
            model: Model name for API
            system_prompt: System prompt for API
            force: Force re-run if results exist
            
        Returns:
            Dictionary with analysis results and diagnosis
        """
        # Generate sample ID if not provided
        if sample_id is None:
            sample_id = Path(vcf_path).stem
            if sample_id.endswith('.vcf'):
                sample_id = sample_id[:-4]
        
        # Check if diagnosis result already exists
        diagnosis_result_path = os.path.join(self.output_dir, f"diagnosis_result_{sample_id}.json")
        # if not force and os.path.exists(diagnosis_result_path):
        #     print(f"Diagnosis result already exists for {sample_id}. Use force=True to overwrite.")
        #     with open(diagnosis_result_path, 'r', encoding='utf-8') as f:
        #         return json.load(f)
        
        try:
            # Step 1: Run Exomiser analysis
            print(f"Step 1: Running Exomiser analysis for {sample_id}")
            exomiser_results = self.run_analysis(vcf_path, hpo_ids, sample_id, force, self.output_dir)
            
            # Step 2: Read Exomiser HTML result paths
            exomiser_html_path = exomiser_results['html']
            # Read and parse Exomiser HTML to extract top gene panels
            top20_panels = extract_gene_panels(exomiser_html_path)
            
            # Step 3: Generate Exomiser summary
            print(f"Step 3: Generating Exomiser summary for {sample_id}")
            exomiser_summary = self.read_exomiser_summary(top20_panels)
            
            # Step 4: Build diagnosis prompt
            user_prompt = self.build_diagnosis_prompt(
                exomiser_summary, 
                patient_info or str(hpo_ids), 
                preliminary_diagnosis
            )
            
            # Step 5: Get diagnosis if API interface is provided
            ai_diagnosis = ""
            if api_interface:
                print(f"Step 3: Running AI diagnosis inference for {sample_id}")
                try:
                    ai_diagnosis = api_interface.get_completion(system_prompt, user_prompt)
                except Exception as e:
                    print(f"API call failed: {e}")
                    ai_diagnosis = "API call failed"
            else:
                print("No API interface provided, skipping AI diagnosis")
            
            # Step 6: Compile results
            final_result = {
                "sample_id": sample_id,
                "vcf_path": vcf_path,
                "hpo_ids": hpo_ids,
                "patient_info": patient_info,
                "preliminary_diagnosis": preliminary_diagnosis,
                "exomiser_results": exomiser_results,
                "exomiser_summary": exomiser_summary,
                "diagnosis_prompt": user_prompt,
                "ai_diagnosis": ai_diagnosis,
                "model_used": model
            }
            
            # Step 7: Save results
            with open(diagnosis_result_path, 'w', encoding='utf-8') as f:
                json.dump(final_result, f, ensure_ascii=False, indent=4)
            
            print(f"Complete analysis saved to {diagnosis_result_path}")
            return final_result
            
        except Exception as e:
            print(f"Error in diagnosis inference for {sample_id}: {e}")
            raise