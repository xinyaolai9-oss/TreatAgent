# Third-party notices

TreatAgent uses or redistributes material derived from third-party resources.
The root Apache License 2.0 and the project CC BY 4.0 grant apply only to rights
held by the TreatAgent copyright holders. They do not supersede upstream
licenses, database rights, terms of use, citation requirements, privacy rights,
or trademark rights.

| Resource | Use in TreatAgent | Upstream terms or license | Repository location |
| --- | --- | --- | --- |
| DrugCentral | Drug indication, target, pharmacology, and structure-derived DrugInfo records; version 54 / 1 November 2023 snapshot | CC BY-SA 4.0 as stated by the upstream DrugCentral project; attribution and ShareAlike requirements apply to covered derivatives | `data/drugcentral/` |
| Mondo Disease Ontology | Disease identifiers, names, synonyms, and normalization | CC BY 4.0 | `data/diseaseinfo/` |
| Open Targets Platform | Target-disease associations used in DiseaseInfo records; release 26.03 | Platform data are marked CC0 1.0, while incorporated upstream sources retain their own terms; users should follow the Open Targets source-licensing table | `data/diseaseinfo/` |
| UniProt | Protein sequences and identifiers used by the DTI tool | CC BY 4.0 for copyrightable database content | `data/dti/uniprot_sequence_cache.json` |
| DeepPurpose 0.1.5 | DTI software dependency and the MPNN-CNN BindingDB checkpoint | DeepPurpose software is BSD-3-Clause; the checkpoint and its training data may also be subject to applicable upstream dataset terms | `data/dti/model_MPNN_CNN/`, `requirements.txt` |
| ADMET-AI | Runtime software dependency for ADMET predictions | MIT License for the upstream software; model and training-dataset terms remain those stated by the upstream project | `requirements.txt`, `environment.yml` |
| ClinicalTrials.gov and benchmark source records | Trial dates, endpoint-derived labels, benchmark records, and derived TrialPrior statistics | Not relicensed by TreatAgent; applicable source terms and any rights in submitted records remain in force | `data/benchmark/`, `data/trial_prior/` |

## Source links

- DrugCentral: <https://github.com/unmtransinfo/DrugCentral-2023>
- Mondo: <https://mondo.monarchinitiative.org/pages/download/>
- Open Targets licence: <https://platform-docs.opentargets.org/licence>
- Open Targets terms of use: <https://platform-docs.opentargets.org/licence/terms-of-use>
- UniProt: <https://www.uniprot.org/help/license>
- DeepPurpose: <https://github.com/kexinhuang12345/DeepPurpose>
- ADMET-AI: <https://github.com/swansonk14/admet_ai>
- ClinicalTrials.gov: <https://clinicaltrials.gov/>

The presence of a name or logo in figures or records does not grant permission
to use the corresponding trademark. Users are responsible for checking the
terms applicable to their intended reuse.
