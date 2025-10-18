from Bio.SeqRecord import SeqRecord
from Bio.SeqFeature import SeqFeature, FeatureLocation
from Bio.Seq import Seq
from Bio import SeqIO
from typing import Optional, List
from .event_bus import bus

class GenomeDocument:
    def __init__(self):
        self.record: Optional[SeqRecord] = None
        self.filepath: Optional[str] = None
        self.dirty: bool = False

    def load(self, path: str):
        self.record = SeqIO.read(path, "genbank")
        self.filepath = path
        self.dirty = False
        bus.publish("record_loaded", record=self.record)

    def set_record(self, record: SeqRecord, path: Optional[str] = None):
        self.record = record
        self.filepath = path
        self.dirty = True
        bus.publish("record_loaded", record=self.record)

    def save(self, path: Optional[str] = None):
        if self.record is None:
            return
        out = path or self.filepath
        if out is None:
            return
        SeqIO.write(self.record, out, "genbank")
        self.filepath = out
        self.dirty = False
        bus.publish("record_saved", path=out)

    # Feature helpers
    def features(self) -> List[SeqFeature]:
        return list(self.record.features) if (self.record and self.record.features) else []

    def update_feature(self, idx: int, ftype: str, start: int, end: int, strand: int, qualifiers: dict):
        feat = self.record.features[idx]
        feat.type = ftype
        feat.location = FeatureLocation(start, end, strand=strand if strand in (-1, 1) else None)
        feat.qualifiers = qualifiers
        self.dirty = True
        bus.publish("features_changed", record=self.record)

    def add_feature(self, ftype="gene", start=0, end=10, strand=1, qualifiers=None):
        if qualifiers is None:
            qualifiers = {}
        feat = SeqFeature(FeatureLocation(start, end, strand=strand if strand in (-1, 1) else None), type=ftype, qualifiers=qualifiers)
        self.record.features.append(feat)
        self.dirty = True
        bus.publish("features_changed", record=self.record)

    def delete_feature(self, idx: int):
        if 0 <= idx < len(self.record.features):
            del self.record.features[idx]
            self.dirty = True
            bus.publish("features_changed", record=self.record)
