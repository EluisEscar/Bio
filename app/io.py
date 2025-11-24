import re
from Bio import SeqIO, Entrez
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from Bio.SeqFeature import SeqFeature, FeatureLocation
from typing import Optional, Tuple, Dict, Any
from .event_bus import bus

def is_valid_email(value: str) -> bool:
    """Comprueba de forma simple si el correo parece válido (usuario@dominio.tld)."""
    value = (value or "").strip()
    return bool(value and re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value))       #comprueba mediante regex

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

def fetch_genbank_from_entrez(
    query: str,
    db: str = "nuccore",
    retmax: int = 5,
    email: str = "",
    api_key: Optional[str] = None,
) -> Tuple[SeqRecord, Dict[str, Any]]:
    """
    Descarga el primer registro GenBank que coincide con la consulta usando NCBI Entrez.

    Retorna una tupla (record, info) donde `info` incluye el accession, id y metadatos básicos
    de la búsqueda realizada.
    """
    term = (query or "").strip()
    if not term:
        raise ValueError("La consulta para NCBI no puede estar vacía.")
    if not is_valid_email(email):
        raise ValueError("Debes proporcionar un correo electrónico con formato válido para NCBI.")

    Entrez.email = email.strip()
    Entrez.api_key = api_key or None

    try:
        with Entrez.esearch(db=db, term=term, retmax=retmax) as search_handle:
            search_result = Entrez.read(search_handle)
    except Exception as exc:
        raise RuntimeError(f"No se pudo consultar NCBI ({db}): {exc}") from exc

    id_list = search_result.get("IdList", [])
    if not id_list:
        raise ValueError(f"No se encontraron resultados en {db} para «{term}».")
    fetch_id = id_list[0]

    try:
        with Entrez.efetch(db=db, id=fetch_id, rettype="gb", retmode="text") as fetch_handle:
            record = SeqIO.read(fetch_handle, "genbank")
    except Exception as exc:
        raise RuntimeError(f"No se pudo descargar el registro {fetch_id} desde NCBI: {exc}") from exc

    accession = record.annotations.get("accessions")
    if isinstance(accession, list) and accession:
        accession = accession[0]
    else:
        accession = record.id or fetch_id

    try:
        total_count = int(search_result.get("Count", "0"))
    except Exception:
        total_count = 0

    info: Dict[str, Any] = {
        "query": term,
        "db": db,
        "count": total_count,
        "matches": id_list,
        "id": fetch_id,
        "accession": accession,
    }
    return record, info
