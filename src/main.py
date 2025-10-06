import streamlit as st
from pathlib import Path
from datetime import datetime, timedelta
from PIL import Image
import shutil

try:
    from . import settings
    from .db import db
    from .excel_io import excel_io
except ImportError:
    import settings
    from db import db
    from excel_io import excel_io


# Configurazione pagina
st.set_page_config(
    page_title="Gestionale Immobiliare",
    page_icon="🏠",
    layout="wide"
)

# Inizializzazione session state
if 'selected_prop_id' not in st.session_state:
    st.session_state.selected_prop_id = None
if 'refresh' not in st.session_state:
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

    # Filtri
    st.sidebar.subheader("🔍 Filtri")
    cerca = st.sidebar.text_input("Cerca (nome, indirizzo, catasto)", "")

    ordina = st.sidebar.selectbox(
        "Ordina per",
        ["nome", "valore_mq DESC", "contratto_fine ASC"]
    )

    solo_affitti = st.sidebar.checkbox("Solo affitti attivi")
    scadenza_60 = st.sidebar.checkbox("Scadenza < 60 giorni")
    non_pagati = st.sidebar.checkbox("Mensilità non pagate")

    # Applica filtri
    filters = {
        'order_by': ordina,
        'solo_affitti': solo_affitti,
        'scadenza_giorni': 60 if scadenza_60 else None,
        'non_pagati': non_pagati
    }

    proprieta = db.get_all_proprieta(filters)

    # Filtra per ricerca testuale (anche su indirizzo e dati catastali)
    if cerca:
        q = cerca.lower()
        proprieta = [
            p for p in proprieta
            if q in str(p.get('nome', '')).lower()
            or q in str(p.get('indirizzo', '')).lower()
            or q in str(p.get('foglio', '')).lower()
            or q in str(p.get('particella', '')).lower()
            or q in str(p.get('subalterno', '')).lower()
            or q in str(p.get('zona_cens', '')).lower()
            or q in str(p.get('categoria', '')).lower()
            or q in str(p.get('classe', '')).lower()
        ]

    st.sidebar.markdown("---")
    st.sidebar.subheader("📋 Elenco")

    for prop in proprieta:
        giorni_scadenza = calcola_giorni_scadenza(prop.get('contratto_fine'))

        # Badge stato
        if prop.get('affittato_a'):
            badge = "🟢" if prop.get('mensilita_pagata') else "🔴"
            affitto_info = f"{badge} {prop.get('affitto_mensile', 0):.0f}€"
        else:
            affitto_info = "⚪ Libero"

        warning = f" ⚠️ {giorni_scadenza}gg" if 0 < giorni_scadenza < 60 else ""



        if st.sidebar.button(
            f"{prop.get('nome')}\n{affitto_info}{warning}",
            key=f"prop_{prop.get('id')}",
            use_container_width=True
        ):
            st.session_state.selected_prop_id = int(prop['id'])
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
        # Immagine
        img_path = settings.IMAGES_DIR / prop['immagine_path'] if prop.get('immagine_path') else None
        if img_path and img_path.exists():
            st.image(str(img_path), use_container_width=True)
        else:
            st.info("📷 Nessuna immagine")

    with col2:
        st.subheader(prop.get('nome'))
        st.write(f"**Indirizzo**: {prop.get('indirizzo')}")

        col_mq1, col_mq2, col_val = st.columns(3)
        col_mq1.metric("MQ Effettivi", f"{prop.get('mq_effettivi', 0):.1f}")
        col_mq2.metric("MQ Commerciali", f"{prop.get('mq_commerciali', 0):.1f}")
        col_val.metric("Valore €/m²", f"{prop.get('valore_mq', 0):.0f}€")

        valore_totale = float(prop.get('mq_commerciali') or 0) * float(prop.get('valore_mq') or 0)
        st.write(f"**Valore Totale**: {valore_totale:,.0f}€")

    # Sezione dettagli catastali estesa
    st.markdown("---")
    st.subheader("📐 Dati catastali")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.write(f"**Foglio:** {prop.get('foglio', '—') or '—'}")
        st.write(f"**Zona cens.:** {prop.get('zona_cens', '—') or '—'}")
    with c2:
        st.write(f"**Particella:** {prop.get('particella', '—') or '—'}")
        st.write(f"**Categoria:** {prop.get('categoria', '—') or '—'}")
    with c3:
        st.write(f"**Subalterno:** {prop.get('subalterno', '—') or '—'}")
        st.write(f"**Classe:** {prop.get('classe', '—') or '—'}")

    st.markdown("---")

    # Dati affitto
    if prop.get('affittato_a'):
        col_aff1, col_aff2 = st.columns(2)

        with col_aff1:
            st.write(f"**Affittato a**: {prop.get('affittato_a')}")
            st.write(f"**Canone mensile**: {prop.get('affitto_mensile', 0):,.2f}€")

        with col_aff2:
            st.write(f"**Contratto**: {prop.get('contratto_inizio')} → {prop.get('contratto_fine')}")

            giorni = calcola_giorni_scadenza(prop.get('contratto_fine'))
            if giorni < 0:
                st.error(f"⏰ SCADUTO da {abs(giorni)} giorni")
            elif giorni < 60:
                st.warning(f"⚠️ Scade tra {giorni} giorni")
            else:
                st.success(f"✅ Scade tra {giorni} giorni")

            if prop.get('mensilita_pagata'):
                st.success("🟢 **Mensilità PAGATA**")
            else:
                st.error("🔴 **Mensilità NON PAGATA**")
    else:
        st.info("⚪ Immobile attualmente libero")

    st.markdown("---")

    # Azioni
    col_edit, col_del, col_pdf = st.columns([1, 1, 2])

    with col_edit:
        if st.button("✏️ Modifica", use_container_width=True):
            st.session_state.edit_mode = prop_id
            st.rerun()

    with col_del:
        if st.button("🗑️ Elimina", use_container_width=True, type="secondary"):
            if st.session_state.get('confirm_delete') == prop_id:
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
            nome = st.text_input("Nome *", value=prop.get('nome', ''))
            indirizzo = st.text_area("Indirizzo *", value=prop.get('indirizzo', ''))
            mq_eff = st.number_input("MQ Effettivi *", min_value=1.0, value=float(prop.get('mq_effettivi', 50)))
            mq_comm = st.number_input("MQ Commerciali *", min_value=1.0, value=float(prop.get('mq_commerciali', 60)))
            valore_mq = st.number_input("Valore €/m² *", min_value=1.0, value=float(prop.get('valore_mq', 2000)))

        with col2:
            affittato_a = st.text_input("Affittato a", value=prop.get('affittato_a', '') or '')
            affitto_mensile = st.number_input("Canone Mensile €", min_value=0.0, value=float(prop.get('affitto_mensile', 0)))

            contratto_inizio = st.date_input(
                "Contratto Inizio",
                value=datetime.fromisoformat(prop['contratto_inizio']).date() if prop.get('contratto_inizio') else None
            )
            contratto_fine = st.date_input(
                "Contratto Fine",
                value=datetime.fromisoformat(prop['contratto_fine']).date() if prop.get('contratto_fine') else None
            )

            mensilita_pagata = st.checkbox("Mensilità Pagata", value=bool(prop.get('mensilita_pagata', 0)))

            immagine = st.file_uploader(
                "Carica Foto",
                type=['jpg', 'jpeg', 'png', 'webp'],
                help=f"Max {settings.MAX_IMAGE_SIZE_MB}MB"
            )

        # --- Sezione Dati catastali (separata) ---
        with st.expander("📐 Dati catastali", expanded=True):
            r1c1, r1c2, r1c3 = st.columns(3)
            with r1c1:
                foglio = st.number_input("Foglio", min_value=0.0, value=float(prop.get('foglio') or 0.0))
                zona_cens = st.text_input("Zona cens.", value=prop.get('zona_cens', '') or '')
            with r1c2:
                particella = st.number_input("Particella", min_value=0.0, value=float(prop.get('particella') or 0.0))
                categoria = st.text_input("Categoria (es. A/2)", value=prop.get('categoria', '') or '')
            with r1c3:
                subalterno = st.number_input("Subalterno", min_value=0.0, value=float(prop.get('subalterno') or 0.0))
                classe = st.text_input("Classe", value=prop.get('classe', '') or '')

        submitted = st.form_submit_button("💾 Salva", type="primary", use_container_width=True)

        if submitted:
            # Validazioni
            if not nome or not indirizzo:
                st.error("❌ Nome e indirizzo sono obbligatori")
                return

            if mq_comm < mq_eff:
                st.error("❌ MQ Commerciali devono essere >= MQ Effettivi")
                return

            # Gestione immagine
            immagine_path = prop.get('immagine_path')
            if immagine:
                ext = Path(immagine.name).suffix
                filename = f"{nome.lower().replace(' ', '_')}_{datetime.now().timestamp()}{ext}"
                img_path = settings.IMAGES_DIR / filename
                with open(img_path, 'wb') as f:
                    f.write(immagine.getbuffer())
                immagine_path = filename

            # Prepara dati
            data = {
                'nome': nome,
                'indirizzo': indirizzo,
                'mq_effettivi': mq_eff,
                'mq_commerciali': mq_comm,
                'valore_mq': valore_mq,
                'affittato_a': affittato_a if affittato_a else None,
                'affitto_mensile': affitto_mensile,
                'contratto_inizio': contratto_inizio.isoformat() if contratto_inizio else None,
                'contratto_fine': contratto_fine.isoformat() if contratto_fine else None,
                'mensilita_pagata': 1 if mensilita_pagata else 0,
                'immagine_path': immagine_path,
                'foglio': foglio if foglio > 0 else None,
                'particella': particella if particella > 0 else None,
                'subalterno': subalterno if subalterno > 0 else None,
                'zona_cens': zona_cens or None,
                'categoria': categoria or None,
                'classe': classe or None,
            }

            try:
                if prop_id:
                    db.update_proprieta(prop_id, data)
                    st.success("✅ Proprietà aggiornata!")
                    st.session_state.edit_mode = None
                else:
                    new_id = db.create_proprieta(data)
                    st.success(f"✅ Proprietà creata! (ID: {new_id})")
                    st.session_state.selected_prop_id = new_id

                st.rerun()
            except Exception as e:
                st.error(f"❌ Errore: {str(e)}")


def render_azioni_globali():
    """Azioni Import/Export/Sync"""
    st.sidebar.markdown("---")
    st.sidebar.subheader("📊 Azioni Globali")

    # Nuovo immobile
    if st.sidebar.button("➕ Nuovo Immobile", use_container_width=True, type="primary"):
        st.session_state.edit_mode = 0
        st.session_state.selected_prop_id = None
        st.rerun()

    # Export Excel
    if st.sidebar.button("📤 Export Excel", use_container_width=True):
        try:
            export_path = settings.DATA_DIR / f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            excel_io.export_to_excel(export_path)

            with open(export_path, 'rb') as f:
                st.sidebar.download_button(
                    "⬇️ Scarica File",
                    f.read(),
                    file_name=export_path.name,
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
            st.sidebar.success("✅ Export completato!")
        except Exception as e:
            st.sidebar.error(f"❌ Errore export: {e}")

    # Import Excel
    uploaded_file = st.sidebar.file_uploader("📥 Import Excel", type=['xlsx'])
    if uploaded_file:
        try:
            temp_path = settings.DATA_DIR / "temp_import.xlsx"
            with open(temp_path, 'wb') as f:
                f.write(uploaded_file.getbuffer())

            count, errors = excel_io.import_from_excel(temp_path)

            if errors:
                st.sidebar.warning(f"⚠️ Importati {count}, {len(errors)} errori:")
                for err in errors[:5]:  # Mostra max 5 errori
                    st.sidebar.text(err)
            else:
                st.sidebar.success(f"✅ Importati {count} immobili!")

            temp_path.unlink()
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"❌ Errore import: {e}")

    # Toggle Sync API
    st.sidebar.markdown("---")
    sync_enabled = st.sidebar.toggle(
        "🔄 Sync API",
        value=settings.SYNC_MODE == "api",
        help="Sincronizza con server remoto"
    )

    if sync_enabled and settings.SYNC_MODE == "local":
        settings.SYNC_MODE = "api"
        st.sidebar.info(f"🌐 Connesso a: {settings.API_BASE_URL}")
    elif not sync_enabled and settings.SYNC_MODE == "api":
        settings.SYNC_MODE = "local"
        st.sidebar.info("💾 Modalità locale")


def main():
    """Main app logic"""
    st.title("🏠 Gestionale Immobiliare")

    # Render sidebar
    render_sidebar()
    render_azioni_globali()

    # Main content
    if st.session_state.get('edit_mode') is not None:
        # Mostra form
        render_form_proprieta(st.session_state.edit_mode if st.session_state.edit_mode > 0 else None)

        if st.button("❌ Annulla"):
            st.session_state.edit_mode = None
            st.rerun()

    elif st.session_state.get('selected_prop_id') is not None:
        # Mostra scheda immobile
        render_scheda_immobile(int(st.session_state.selected_prop_id))

    if 'edit_mode' not in st.session_state or st.session_state.get('edit_mode') is None:
        # Home / Dashboard
        st.info("👈 Seleziona un immobile dalla barra laterale o crea uno nuovo")

        # Statistiche rapide
        proprieta = db.get_all_proprieta()

        if proprieta:
            col1, col2, col3, col4 = st.columns(4)

            affitti_attivi = [p for p in proprieta if p.get('affittato_a')]
            non_pagati = [p for p in affitti_attivi if not p.get('mensilita_pagata')]
            scadenze_vicine = [p for p in proprieta if calcola_giorni_scadenza(p.get('contratto_fine')) < 60]

            col1.metric("📋 Totale Immobili", len(proprieta))
            col2.metric("🏠 Affitti Attivi", len(affitti_attivi))
            col3.metric("🔴 Mensilità Non Pagate", len(non_pagati))
            col4.metric("⚠️ Scadenze < 60gg", len(scadenze_vicine))

            # Entrate mensili
            entrate_mensili = sum(float(p.get('affitto_mensile') or 0) for p in affitti_attivi)
            st.metric("💰 Entrate Mensili Totali", f"{entrate_mensili:,.2f}€")


if __name__ == "__main__":
    main()
