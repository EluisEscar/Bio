from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from Bio.SeqFeature import SeqFeature, FeatureLocation
from typing import Optional
from .event_bus import bus

def load_genbank(path: str):
    rec = SeqIO.read(path, "genbank")
    bus.publish("record_loaded", record=rec)
    return rec

def save_genbank(record: SeqRecord, path: str):
    SeqIO.write(record, path, "genbank")
    bus.publish("record_saved", path=path)

def make_demo_record():
    # Pequeño plásmido sintético de 3000 bp con 3 features
    seq = Seq("ATG" * 1000)  # 3000 bp
    rec = SeqRecord(seq, id="DEMO001", name="DemoPlasmid", description="Plásmido sintético de ejemplo")
    rec.annotations["molecule_type"] = "DNA"
    rec.annotations["topology"] = "circular"
    rec.annotations["data_file_division"] = "BCT"
    rec.annotations["date"] = "01-JAN-2000"
    rec.features = []

    rec.features.append(SeqFeature(FeatureLocation(100, 450, strand=1), type="gene", qualifiers={"gene": ["repA"], "note": ["origen de replicación"]}))
    rec.features.append(SeqFeature(FeatureLocation(800, 1500, strand=-1), type="CDS", qualifiers={"product": ["protein X"], "note": ["enzima hipotética"]}))
    rec.features.append(SeqFeature(FeatureLocation(2000, 2300, strand=1), type="promoter", qualifiers={"note": ["promotor fuerte"]}))
    return rec
