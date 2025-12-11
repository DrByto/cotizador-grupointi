import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import random

# --- Configuración de la Página ---
# --- Configuración de la Página ---
st.set_page_config(page_title="Cotizador de reservas GRUPO INTI", layout="wide")

# --- Funciones ---

@st.cache_data
def load_data(filepath):
    """Carga y limpia los datos del archivo CSV."""
    try:
        # Asumiendo delimitador ';' según la vista del archivo
        df = pd.read_csv(filepath, sep=';', encoding='utf-8-sig') # Usar utf-8-sig para manejar BOM
        
        # Limpieza de columnas
        df['Valor'] = df['Valor'].astype(str).str.replace('$', '', regex=False).str.replace(',', '', regex=False)
        df['Valor'] = pd.to_numeric(df['Valor'], errors='coerce').fillna(0.0)
        
        # Asegurar tipos
        df['Ano'] = df['Ano'].astype(str)
        df['AGENCIA'] = df['AGENCIA'].fillna('').astype(str)
        df['Atributo'] = df['Atributo'].fillna('').astype(str)
        return df
    except Exception as e:
        st.error(f"Error cargando el archivo: {e}")
        return pd.DataFrame()

def generate_reservation_code():
    """Genera un código de reserva aleatorio tipo R-12345."""
    return f"R-{random.randint(10000, 99999)}"

# --- Interfaz Principal ---

st.title("🏨 Cotizador de Reservas - GRUPO INTI")

# 1. Configuración de Fechas
st.sidebar.header("1. Configuración")

# Fechas Globales
col_date1, col_date2 = st.columns(2)
with col_date1:
    checkin_date = st.date_input("Fecha Check-in", datetime.now() + timedelta(days=1))
with col_date2:
    checkout_date = st.date_input("Fecha Check-out", checkin_date + timedelta(days=1))

if checkin_date >= checkout_date:
    st.error("La fecha de Check-out debe ser posterior al Check-in.")
    total_nights = 0
else:
    total_nights = (checkout_date - checkin_date).days
    st.sidebar.info(f"Noches: {total_nights}")

# Lógica de Año
if checkin_date.month < 4:
    calculated_year = str(checkin_date.year - 1)
else:
    calculated_year = str(checkin_date.year)

st.sidebar.text(f"Tarifario: {calculated_year}")

DATA_FILE = "Master_Tarifas.csv"
df = load_data(DATA_FILE)

if not df.empty:
    available_years = df['Ano'].unique()
    if calculated_year not in available_years:
        st.warning(f"No hay tarifas para {calculated_year}. Seleccione manual.")
        selected_year = st.sidebar.selectbox("Seleccionar Año", sorted(available_years))
    else:
        selected_year = calculated_year
    
    agencies = sorted(df[df['Ano'] == selected_year]['AGENCIA'].unique())
    selected_agency = st.sidebar.selectbox("Agencia", agencies)

    filtered_df = df[(df['Ano'] == selected_year) & (df['AGENCIA'] == selected_agency)]
    
    all_items = filtered_df['Atributo'].unique().tolist()
    totos_items = [item for item in all_items if item.startswith('Totos_')]
    room_items = [item for item in all_items if not item.startswith('Totos_')]
    
else:
    st.warning("Error carga datos.")
    st.stop()

# 2. Selección de Servicios
st.header("2. Selección de Servicios")

if 'selected_rooms' not in st.session_state:
    st.session_state.selected_rooms = []

def calculate_igv_breakdown(base_total, is_national):
    if is_national:
        val_base = base_total / 1.1
        val_total = val_base * 1.28
        return {"is_national": True, "base_original": base_total, "val_venta": val_base, "total_final": val_total}
    else:
        return {"is_national": False, "base_original": base_total, "val_venta": base_total, "total_final": base_total}

# --- Sección Habitaciones ---
st.subheader("Habitaciones (Alojamiento)")

hotel_category = st.radio("Sede / Hotel", ["Classic", "Boutique"], horizontal=True)
current_room_items = [item for item in room_items if hotel_category in item]

with st.form("add_room_form"):
    c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
    with c1:
        room_type = st.selectbox("Tipo de Habitación", current_room_items)
        
        # Selector de Tipo de Cama para ambigüedades
        bed_options = []
        if "SimpleMat" in room_type:
             bed_options = ["Simple", "Matrimonial"]
        elif "DobleMat" in room_type:
             bed_options = ["Doble", "Matrimonial"]
        
        bed_selection = None
        if bed_options:
            bed_selection = st.radio("Configuración de Cama", bed_options, horizontal=True)

    with c2:
        qty_room = st.number_input("Cant.", min_value=1, value=1, step=1, key="q_room")
    with c3:
        is_nat_room = st.checkbox("Nacional?", help="Aplica IGV 18%", key="nat_room")
    with c4:
        sub_room = st.form_submit_button("Agregar")
    
    if sub_room and room_type and total_nights > 0:
        price_row = filtered_df[filtered_df['Atributo'] == room_type]
        if not price_row.empty:
            unit_val = price_row.iloc[0]['Valor']
            
            # Subtotal incluye noches para alojamiento
            base_subtotal = unit_val * qty_room * total_nights
            
            calc = calculate_igv_breakdown(base_subtotal, is_nat_room)
            
            # Nombre limpio para guardar
            st.session_state.selected_rooms.append({
                "Categoria": "Habitacion",
                "Tipo": room_type,
                "BedSelection": bed_selection,
                "Cantidad": qty_room,
                "IsNational": is_nat_room,
                "DetallePrecio": calc
            })
            st.success(f"Agregado: {room_type} ({qty_room} x {total_nights} noches)")
    elif sub_room and total_nights <= 0:
        st.error("Verifique fechas.")

# --- Sección Totos ---
st.subheader("Servicios Totos (Restaurante/Otros)")
with st.form("add_totos_form"):
    c1, c2, c3, c4, c5 = st.columns([3, 1, 1, 1, 1]) # Columnas ajustadas para la fecha
    with c1:
        totos_type = st.selectbox("Servicio Totos", totos_items)
    with c2:
        totos_meal = st.radio("Horario", ["Almuerzo", "Cena"], horizontal=True)
    with c3:
        # Selector de Fecha (Default Checkin)
        # Limitamos entre checkin y checkout para logica simple, o libre
        totos_date = st.date_input("Fecha Servicio", value=checkin_date, min_value=checkin_date, max_value=checkout_date)
    with c4:
        qty_totos = st.number_input("Cant.", min_value=1, value=1, step=1, key="q_totos")
    with c5:
        sub_totos = st.form_submit_button("Agregar")
    
    if sub_totos and totos_type:
        price_row = filtered_df[filtered_df['Atributo'] == totos_type]
        if not price_row.empty:
            unit_val = price_row.iloc[0]['Valor']
            
            # Totos NO multiplica por noches (es por servicio puntual)
            base_subtotal = unit_val * qty_totos 
            
            calc = calculate_igv_breakdown(base_subtotal, False) 
            
            st.session_state.selected_rooms.append({
                "Categoria": "Totos",
                "Tipo": totos_type,
                "Cantidad": qty_totos,
                "TotosMeal": totos_meal,
                "TotosDate": totos_date, # Guardamos la fecha
                "IsNational": False,
                "DetallePrecio": calc
            })
            st.success(f"Agregado Totos {totos_date.strftime('%d/%m')}")

# Resumen
if st.session_state.selected_rooms:
    st.write("### Resumen")
    index_to_remove = -1
    for i, item in enumerate(st.session_state.selected_rooms):
        c1, c2, c3, c4, c5 = st.columns([4, 1, 2, 2, 1])
        
        # Display Name smart
        dname = item['Tipo']
        if item.get('BedSelection'):
             dname += f" ({item['BedSelection']})"
        elif item.get('TotosMeal'):
             d_str = item['TotosDate'].strftime('%d/%m')
             dname += f" ({item['TotosMeal']}) ({d_str})"
             
        c1.write(dname)
        c2.write(item['Cantidad'])
        c3.write("Nacional" if item['IsNational'] else "-")
        c4.write(f"${item['DetallePrecio']['total_final']:,.2f}")
        if c5.button("🗑️", key=f"del_{i}"):
            index_to_remove = i
            
    if index_to_remove >= 0:
        st.session_state.selected_rooms.pop(index_to_remove)
        st.rerun()

    if st.button("Borrar Todo"):
         st.session_state.selected_rooms = []
         st.rerun()

# 3. Confirmación
st.header("3. Confirmación")

total_rooms_count = sum(x['Cantidad'] for x in st.session_state.selected_rooms if x['Categoria'] == 'Habitacion')
days_prior = 45 if total_rooms_count > 3 else 20
payment_deadline = checkin_date - timedelta(days=days_prior)

def clean_room_name(raw_name, bed_sel):
    # E.g. "Classic_DobleMat", "Boutique_DobleMat_Rio"
    # Remove prefix
    nobrand = raw_name.replace("Classic_", "").replace("Boutique_", "")
    
    suffix = ""
    if "_Rio" in nobrand:
        suffix = " VISTA RIO"
        nobrand = nobrand.replace("_Rio", "")
    elif "_Ciudad" in nobrand:
        suffix = " VISTA CIUDAD"
        nobrand = nobrand.replace("_Ciudad", "")
        
    # Bed override
    main_type = nobrand.upper()
    if bed_sel:
        main_type = bed_sel.upper()
    else:
        # Fallback mappings if no bed selection but we want clean text
        if "DOBLEMAT" in main_type: main_type = "MATRIMONIAL/DOBLE" # Should trigger selector usually
        elif "SIMPLEMAT" in main_type: main_type = "SIMPLE/MATRIMONIAL"
        elif "TRIPLE" in main_type: main_type = "TRIPLE"
        elif "GUIA" in main_type: main_type = "GUIA"
        
    return f"HAB. {main_type}{suffix}"

if st.button("Generar Confirmación Detallada"):
    if not st.session_state.selected_rooms:
        st.warning("Sin items.")
    else:
        has_boutique = any('Boutique' in x['Tipo'] for x in st.session_state.selected_rooms)
        hotel_header = "Es un placer recibirte en el Hotel HATUN INTI BOUTIQUE- 04 ESTRELLAS(Imperio de los Incas N° 606, Aguas Calientes- Cusco)" if has_boutique else "Es un placer recibirte en el Hotel HATUN INTI CLASSIC-03 ESTRELLAS (Av. Pachacútec 606, Aguas Calientes)"
            
        std_rooms = []
        guide_rooms = []
        nat_rooms_base = 0.0
        nat_rooms_total = 0.0
        totos_items = []
        
        all_room_texts = []
        
        for item in st.session_state.selected_rooms:
            qty = item['Cantidad']
            qty_fmt = f"{qty:02d}"
            
            calc = item['DetallePrecio']
            total_final = calc['total_final']
            base_orig = calc['base_original']
            
            if item['Categoria'] == 'Habitacion':
                clean_name = clean_room_name(item['Tipo'], item.get('BedSelection'))
                all_room_texts.append(f"{qty_fmt} {clean_name}")
                
                is_guide = 'GUIA' in item['Tipo'].upper()
                if is_guide:
                    guide_rooms.append(total_final)
                elif item['IsNational']:
                    nat_rooms_base += base_orig
                    nat_rooms_total += total_final
                else:
                    std_rooms.append(total_final)
            
            elif item['Categoria'] == 'Totos':
                # Agregar Date: (DD/MM)
                meal = item.get('TotosMeal', '').upper()
                date_val = item.get('TotosDate')
                date_str = date_val.strftime("%d/%m") if date_val else ""
                
                name_clean = item['Tipo'].replace('Totos_', '').replace('_', ' ').upper()
                
                # Format: MEDIA PENSION CENA 08 PAX (05/12) -> wait, user req: 
                # MEDIA PENSION CENA 08 PAX + 01 GUIA (05/12): $153.00
                # My logic: {name} ({meal}) ({date}) ...
                parts = [name_clean]
                if meal: parts.append(meal)
                if date_str: parts.append(f"({date_str})")
                
                name_display = " ".join(parts)
                totos_items.append((qty, name_display, total_final))

        acomodacion_str = " + ".join(all_room_texts) if all_room_texts else "NINGUNA"
        
        liquidation_lines = []
        if std_rooms:
            liquidation_lines.append(f"      LIQUIDACION ALOJAMIENTO                          :  $ {sum(std_rooms):,.2f} DÓLARES")
        if guide_rooms:
            liquidation_lines.append(f"          LIQUIDACION ALOJAMIENTO GUIA                 : $ {sum(guide_rooms):,.2f} DÓLARES")
        if nat_rooms_total > 0:
            # LIQUIDACION ALOJAMIENTO GRAVADO : $116.36 DÓLARES (100+IGV18%)
            liquidation_lines.append(f"LIQUIDACION ALOJAMIENTO GRAVADO : ${nat_rooms_total:,.2f} DÓLARES ({nat_rooms_base:,.2f}+IGV18%)")
            
        for qty, name, tot in totos_items:
            liquidation_lines.append(f"          {name} {qty:02d} PAX : ${tot:,.2f} DÓLARES")

        liquidation_block = "\n\n".join(liquidation_lines)
        
        res_code = generate_reservation_code()
        checkin_str = checkin_date.strftime("%d/%m/%Y")
        checkout_str = checkout_date.strftime("%d/%m/%Y")
        deadline_str = payment_deadline.strftime("%d/%m/%Y")

        final_text = f"""Buen día:   MEDIANTE LA PRESENTE CONFIRMO LA RESERVA EN MENCIÓN

      {hotel_header}

     IMPORTANTE: Una vez recibido el correo, verifique que la fecha enviada sea la correcta, a fin de evitar inconvenientes por falta de disponibilidad.

      CÓDIGO DE RESERVA  / NOMBRE PAX/  FILE  : {res_code}

      ACOMODACIÓN   (TIPO DE HABITACIÓN)       : {acomodacion_str}

      CHECK-IN         13 pm                                          : {checkin_str}

      CHECK-OUT       10 am                                      : {checkout_str}

      DESAYUNO -HORARIO  5 am a 10 am              : INCLUIDO

{liquidation_block}

      FECHA LÍMITE DE CONFIRMACIÓN Y PAGO:   {deadline_str}"""
        
        st.success("Confirmación Generada!")
        st.text_area("Copiar Texto:", value=final_text, height=500)

