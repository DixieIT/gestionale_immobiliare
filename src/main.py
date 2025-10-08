import streamlit as st
from pathlib import Path
from datetime import datetime
import tempfile

try:
    from . import settings
    from .db import db
    from .excel_io import excel_io
except ImportError:
    import settings
    from db import db
    from excel_io import excel_io


# Configurazione pagina
st.set_page_config(page_title="Gestionale Immobiliare", page_icon="🏠", layout="wide")

# Inizializzazione session state
if "selected_prop_id" not in st.session_state:
    st.session_state.selected_prop_id = None
if "refresh" not in st.session_state:
    st.session_state.refresh = 0


def calcola_giorni_scadenza(data_fine: str) -> int:
    """Calcola giorni alla scadenza"""
    if not data_fine:
        return 999
    try:
        scadenza = datetime.fromisoformat(data_fine).date()
        return (scadenza - datetime.now().date()).days
    except Exception:
        return 999


def render_sidebar():
    """Sidebar con elenco proprietà e filtri"""
    st.sidebar.title("🏠 Immobili")

    st.sidebar.subheader("🔍 Filtri")
    cerca = st.sidebar.text_input("Cerca (nome, indirizzo, catasto)", "")
    ordina = st.sidebar.selectbox("Ordina per", ["nome", "valore_mq DESC", "contratto_fine ASC"])
    solo_affitti = st.sidebar.checkbox("Solo affitti attivi")
    scadenza_60 = st.sidebar.checkbox("Scadenza < 60 giorni")
    non_pagati = st.sidebar.checkbox("Mensilità non pagate")

    filters = {
        "order_by": ordina,
        "solo_affitti": solo_affitti,
        "scadenza_giorni": 60 if scadenza_60 else None,
        "non_pagati": non_pagati,
    }

    proprieta = db.get_all_proprieta(filters)

    if cerca:
        q = cerca.lower()
        proprieta = [
            p for p in proprieta
            if any(q in str(p.get(k, "")).lower() for k in ["nome", "indirizzo", "foglio", "particella", "subalterno", "zona_cens", "categoria", "classe"])
        ]

    st.sidebar.markdown("---")
    st.sidebar.subheader("📋 Elenco")

    for prop in proprieta:
        giorni_scadenza = calcola_giorni_scadenza(prop.get("contratto_fine"))
        badge = "🟢" if prop.get("mensilita_pagata") else "🔴" if prop.get("affittato_a") else "⚪"
        affitto_info = f"{badge} {prop.get('affitto_mensile', 0):.0f}€" if prop.get("affittato_a") else "⚪ Libero"
        warning = f" ⚠️ {giorni_scadenza}gg" if 0 < giorni_scadenza < 60 else ""

        if st.sidebar.button(f"{prop.get('nome')}\n{affitto_info}{warning}", key=f"prop_{prop.get('id')}", width="stretch"):
            st.session_state.selected_prop_id = int(prop["id"])
            st.session_state.edit_mode = None
            st.session_state.confirm_delete = None


def render_scheda_immobile(prop_id: int):
    """Render scheda dettagliata immobile"""
    prop = db.get_proprieta_by_id(prop_id)
    if not prop:
        st.error("Proprietà non trovata")
        return

    col1, col2 = st.columns([1, 2])
    with col1:
        img_url = prop.get("immagine_url")
        if not img_url and prop.get("immagine_path"):
            try:
                img_url = db.get_signed_piantina_url(prop["id"], expires_seconds=3600)
            except Exception:
                img_url = None

        if img_url:
            st.image(img_url, width="stretch")
        else:
            st.info("📷 Nessuna immagine")

    with col2:
        st.subheader(prop.get("nome"))
        st.write(f"**Indirizzo:** {prop.get('indirizzo')}")
        col_mq1, col_mq2, col_val = st.columns(3)
        col_mq1.metric("MQ Effettivi", f"{prop.get('mq_effettivi', 0):.1f}")
        col_mq2.metric("MQ Commerciali", f"{prop.get('mq_commerciali', 0):.1f}")
        col_val.metric("Valore €/m²", f"{prop.get('valore_mq', 0):.0f}€")

        valore_totale = float(prop.get("mq_commerciali") or 0) * float(prop.get("valore_mq") or 0)
        st.write(f"**Valore Totale:** {valore_totale:,.0f}€")
        st.write(f"**Quota:** {prop.get('quota', '—') or '—'}")

    st.markdown("---")
    st.subheader("📐 Dati catastali")
    c1, c2, c3 = st.columns(3)
    c1.write(f"**Foglio:** {prop.get('foglio', '—') or '—'}")
    c1.write(f"**Zona cens.:** {prop.get('zona_cens', '—') or '—'}")
    c2.write(f"**Particella:** {prop.get('particella', '—') or '—'}")
    c2.write(f"**Categoria:** {prop.get('categoria', '—') or '—'}")
    c3.write(f"**Subalterno:** {prop.get('subalterno', '—') or '—'}")
    c3.write(f"**Classe:** {prop.get('classe', '—') or '—'}")

    st.markdown("---")

    if prop.get("affittato_a"):
        col_aff1, col_aff2 = st.columns(2)
        with col_aff1:
            st.write(f"**Affittato a:** {prop.get('affittato_a')}")
            st.write(f"**Canone mensile:** {prop.get('affitto_mensile', 0):,.2f}€")
        with col_aff2:
            st.write(f"**Contratto:** {prop.get('contratto_inizio')} → {prop.get('contratto_fine')}")
            giorni = calcola_giorni_scadenza(prop.get("contratto_fine"))
            if giorni < 0:
                st.error(f"⏰ SCADUTO da {abs(giorni)} giorni")
            elif giorni < 60:
                st.warning(f"⚠️ Scade tra {giorni} giorni")
            else:
                st.success(f"✅ Scade tra {giorni} giorni")

            st.success("🟢 Mensilità PAGATA" if prop.get("mensilita_pagata") else "🔴 Mensilità NON PAGATA")
    else:
        st.info("⚪ Immobile attualmente libero")

    # --- Contratto PDF ---
    st.markdown("---")
    st.subheader("📄 Contratto")
    contratto_url = prop.get("contratto_url")
    if not contratto_url and prop.get("contratto_path"):
        try:
            contratto_url = db.get_signed_contratto_url(prop["id"], expires_seconds=3600)
        except Exception:
            contratto_url = None

    if contratto_url:
        st.link_button("📄 Apri PDF", contratto_url, width="stretch")
    else:
        st.info("Nessun contratto caricato")

    st.markdown("---")

    col_edit, col_del, _ = st.columns([1, 1, 2])
    with col_edit:
        if st.button("✏️ Modifica", width="stretch"):
            st.session_state.edit_mode = prop_id
            st.rerun()
    with col_del:
        if st.button("🗑️ Elimina", width="stretch", type="secondary"):
            if st.session_state.get("confirm_delete") == prop_id:
                db.delete_proprieta(prop_id)
                st.session_state.selected_prop_id = None
                st.session_state.confirm_delete = None
                st.success("✅ Eliminato!")
                st.rerun()
            else:
                st.session_state.confirm_delete = prop_id
                st.warning("⚠️ Clicca di nuovo per confermare")


def render_form_proprieta(prop_id: int = None):
    """Form CRUD proprietà"""
    prop = db.get_proprieta_by_id(prop_id) if prop_id else {}

    with st.form("form_proprieta"):
        st.subheader("➕ Nuova Proprietà" if not prop_id else "✏️ Modifica Proprietà")
        col1, col2 = st.columns(2)

        with col1:
            nome = st.text_input("Nome *", value=prop.get("nome", ""))
            indirizzo = st.text_area("Indirizzo *", value=prop.get("indirizzo", ""))
            mq_eff = st.number_input("MQ Effettivi *", min_value=1.0, value=float(prop.get("mq_effettivi", 50)))
            mq_comm = st.number_input("MQ Commerciali *", min_value=1.0, value=float(prop.get("mq_commerciali", 60)))
            valore_mq = st.number_input("Valore €/m² *", min_value=1.0, value=float(prop.get("valore_mq", 2000)))

        with col2:
            affittato_a = st.text_input("Affittato a", value=prop.get("affittato_a", ""))
            affitto_mensile = st.number_input("Canone Mensile €", min_value=0.0, value=float(prop.get("affitto_mensile", 0)))
            contratto_inizio = st.date_input("Contratto Inizio", value=datetime.fromisoformat(prop["contratto_inizio"]).date() if prop.get("contratto_inizio") else None)
            contratto_fine = st.date_input("Contratto Fine", value=datetime.fromisoformat(prop["contratto_fine"]).date() if prop.get("contratto_fine") else None)
            mensilita_pagata = st.checkbox("Mensilità Pagata", value=bool(prop.get("mensilita_pagata", 0)))
            immagine = st.file_uploader("Carica Foto", type=["jpg", "jpeg", "png", "webp"])
            contratto_pdf = st.file_uploader("Carica Contratto (PDF)", type=["pdf"])

        with st.expander("📐 Dati catastali", expanded=True):
            r1c1, r1c2, r1c3 = st.columns(3)
            foglio = r1c1.number_input("Foglio", min_value=0.0, value=float(prop.get("foglio") or 0.0))
            zona_cens = r1c1.text_input("Zona cens.", value=prop.get("zona_cens", ""))
            particella = r1c2.number_input("Particella", min_value=0.0, value=float(prop.get("particella") or 0.0))
            categoria = r1c2.text_input("Categoria (es. A/2)", value=prop.get("categoria", ""))
            subalterno = r1c3.number_input("Subalterno", min_value=0.0, value=float(prop.get("subalterno") or 0.0))
            classe = r1c3.text_input("Classe", value=prop.get("classe", ""))
            quota = st.text_input("Quota", value=prop.get("quota", ""))

        submitted = st.form_submit_button("💾 Salva", type="primary", width="stretch")

        if submitted:
            if not nome or not indirizzo:
                st.error("❌ Nome e indirizzo sono obbligatori")
                return
            if mq_comm < mq_eff:
                st.error("❌ MQ Commerciali devono essere >= MQ Effettivi")
                return

            data = {
                "nome": nome, "indirizzo": indirizzo,
                "mq_effettivi": mq_eff, "mq_commerciali": mq_comm, "valore_mq": valore_mq,
                "affittato_a": affittato_a or None, "affitto_mensile": affitto_mensile,
                "contratto_inizio": contratto_inizio.isoformat() if contratto_inizio else None,
                "contratto_fine": contratto_fine.isoformat() if contratto_fine else None,
                "mensilita_pagata": 1 if mensilita_pagata else 0,
                "foglio": foglio or None, "particella": particella or None, "subalterno": subalterno or None,
                "zona_cens": zona_cens or None, "categoria": categoria or None, "classe": classe or None,
                "quota": quota or None,
            }

            try:
                target_id = prop_id or db.create_proprieta(data)
                if prop_id:
                    db.update_proprieta(prop_id, data)

                if immagine:
                    ext = Path(immagine.name).suffix.lower()
                    filename = f"{nome.lower().replace(' ', '_')}_{int(datetime.now().timestamp())}{ext}"
                    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                        tmp.write(immagine.getbuffer())
                        tmp_path = tmp.name
                    db.upload_piantina_and_link(prop_id=target_id, local_file_path=tmp_path, filename=filename, make_public_url=True)
                    Path(tmp_path).unlink(missing_ok=True)

                if contratto_pdf:
                    filename = f"contratto_{int(datetime.now().timestamp())}.pdf"
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                        tmp.write(contratto_pdf.getbuffer())
                        tmp_path = tmp.name
                    db.upload_contratto_and_link(prop_id=target_id, local_file_path=tmp_path, filename=filename, make_public_url=True)
                    Path(tmp_path).unlink(missing_ok=True)

                st.success("✅ Proprietà salvata!")
                st.session_state.edit_mode = None
                st.session_state.selected_prop_id = target_id
                st.rerun()
            except Exception as e:
                st.error(f"❌ Errore: {e}")


def render_azioni_globali():
    """Azioni Import/Export/Sync"""
    st.sidebar.markdown("---")
    st.sidebar.subheader("📊 Azioni Globali")

    if st.sidebar.button("➕ Nuovo Immobile", width="stretch", type="primary"):
        st.session_state.edit_mode = 0
        st.session_state.selected_prop_id = None
        st.rerun()

    if st.sidebar.button("📤 Export Excel", width="stretch"):
        try:
            export_path = settings.DATA_DIR / f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            excel_io.export_to_excel(export_path)
            with open(export_path, "rb") as f:
                st.sidebar.download_button("⬇️ Scarica File", f.read(), file_name=export_path.name)
            st.sidebar.success("✅ Export completato!")
        except Exception as e:
            st.sidebar.error(f"❌ Errore export: {e}")

    uploaded_file = st.sidebar.file_uploader("📥 Import Excel", type=["xlsx"])
    if uploaded_file:
        try:
            temp_path = settings.DATA_DIR / "temp_import.xlsx"
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            count, errors = excel_io.import_from_excel(temp_path)
            if errors:
                st.sidebar.warning(f"⚠️ Importati {count}, {len(errors)} errori.")
            else:
                st.sidebar.success(f"✅ Importati {count} immobili!")
            temp_path.unlink()
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"❌ Errore import: {e}")


def main():
    st.title("🏠 Gestionale Immobiliare")
    render_sidebar()
    render_azioni_globali()

    if st.session_state.get("edit_mode") is not None:
        render_form_proprieta(st.session_state.edit_mode if st.session_state.edit_mode > 0 else None)
        if st.button("❌ Annulla"):
            st.session_state.edit_mode = None
            st.rerun()
    elif st.session_state.get("selected_prop_id") is not None:
        render_scheda_immobile(int(st.session_state.selected_prop_id))
    else:
        st.info("👈 Seleziona un immobile o creane uno nuovo")
        proprieta = db.get_all_proprieta()
        if proprieta:
            col1, col2, col3, col4 = st.columns(4)
            affitti = [p for p in proprieta if p.get("affittato_a")]
            non_pagati = [p for p in affitti if not p.get("mensilita_pagata")]
            scadenze = [p for p in proprieta if calcola_giorni_scadenza(p.get("contratto_fine")) < 60]
            col1.metric("📋 Totale", len(proprieta))
            col2.metric("🏠 Affitti", len(affitti))
            col3.metric("🔴 Non Pagate", len(non_pagati))
            col4.metric("⚠️ Scadenze <60gg", len(scadenze))
            entrate = sum(float(p.get("affitto_mensile") or 0) for p in affitti)
            st.metric("💰 Entrate Mensili", f"{entrate:,.2f}€")


if __name__ == "__main__":
    main()
