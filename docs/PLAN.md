# Receipt Extractor

## 1. Qué es

Un servicio (API) que recibe la **foto de una boleta o factura peruana** y devuelve sus **datos en formato JSON**.

Es un servicio de una sola responsabilidad: **extraer datos**. Lo que se haga después con ese JSON (guardarlo, exportarlo a Excel, usarlo en una rendición de cuentas) lo decide el sistema que lo consuma.

```
Foto de boleta  ──►  POST /receipts/extract  ──►  JSON con los datos
```

---

## 2. Qué hace

- **Recibe una imagen** (JPG o PNG) de una boleta, factura, nota de crédito/débito o ticket.
- **Extrae los datos** del comprobante usando un modelo de IA con visión (Gemini al inicio).
- **Lee el código QR** de SUNAT cuando la boleta lo tiene, y lo usa para confirmar los datos principales (es más confiable que la lectura de la IA).
- **Valida los datos** con reglas peruanas (RUC, IGV, totales, serie, cliente).
- **Reintenta una vez** si la validación encuentra un error, indicándole a la IA qué no cuadró.
- **Avisa cuando algo no está bien** (`needs_review: true`) en vez de inventar datos. Si un campo no se puede leer, queda vacío (`null`).
- **Informa el costo** de cada extracción (tokens usados).
- **Prepara la imagen** antes de enviarla: la endereza y reduce su tamaño para gastar menos.

## 3. Qué NO hace

- No guarda las imágenes.
- No guarda los datos (no tiene base de datos).
- No exporta a Excel ni CSV.
- No procesa lotes de muchas boletas a la vez.
- No acepta PDF (por ahora).

Todo eso puede construirse después, en otro sistema que use este servicio.

---

## 4. Datos que devuelve

### Datos del comprobante

| Campo | Qué es |
|---|---|
| `document_type` | Tipo: factura (`invoice`), boleta (`receipt`), nota de crédito, nota de débito, ticket u otro |
| `series` | Serie (F001, B001, o 0001 si es física) |
| `number` | Número correlativo |
| `issue_date` | Fecha de emisión |
| `currency` | Moneda: soles (`PEN`) o dólares (`USD`) |
| `issuer_ruc` | RUC de quien emite |
| `issuer_name` | Razón social de quien emite |
| `customer_doc_type` | Tipo de documento del cliente: DNI, RUC, carné de extranjería o pasaporte |
| `customer_doc_number` | Número de documento del cliente |
| `customer_name` | Nombre o razón social del cliente |
| `taxable_amount` | Op. gravada (base sin IGV) |
| `exempt_amount` | Op. exonerada |
| `unaffected_amount` | Op. inafecta |
| `discount_amount` | Descuentos |
| `igv` | IGV |
| `other_charges` | Otros cargos: impuesto a bolsas (ICBPER), propinas, recargos |
| `total` | Importe total |
| `items` | Detalle: descripción, cantidad, precio unitario, descuento y total de cada producto |

### Información de la extracción

| Campo | Qué es |
|---|---|
| `source` | De dónde salieron los datos: solo IA (`llm`) o IA confirmada con el QR (`llm+qr`) |
| `issues` | Lista de problemas encontrados, cada uno con el campo, el mensaje y si es error o advertencia |
| `needs_review` | `true` si hay algún error: una persona debería revisarlo |
| `usage` | Modelo usado y tokens consumidos |

### Ejemplo

```json
{
  "receipt": {
    "document_type": "receipt",
    "series": "B001",
    "number": "4521",
    "issue_date": "2026-10-05",
    "currency": "PEN",
    "issuer_ruc": "20100070970",
    "issuer_name": "SUPERMERCADOS PERUANOS S.A.",
    "customer_doc_type": "DNI",
    "customer_doc_number": "71234567",
    "customer_name": "JUAN PEREZ",
    "taxable_amount": 38.14,
    "exempt_amount": null,
    "unaffected_amount": null,
    "discount_amount": 5.00,
    "igv": 6.86,
    "other_charges": null,
    "total": 45.00,
    "items": [
      { "description": "LECHE GLORIA 1L", "quantity": 2, "unit_price": 5.50, "discount": null, "total": 11.00 },
      { "description": "ACEITE PRIMOR 1L", "quantity": 1, "unit_price": 39.00, "discount": 5.00, "total": 34.00 }
    ]
  },
  "source": "llm+qr",
  "issues": [],
  "needs_review": false,
  "usage": { "model": "gemini-flash-latest", "input_tokens": 1850, "output_tokens": 420 }
}
```

---

## 5. Reglas de validación

| Regla | Si no se cumple |
|---|---|
| Debe tener tipo, fecha, RUC del emisor y total | Error |
| El RUC del emisor debe ser válido (11 dígitos y dígito verificador correcto) | Error |
| El IGV debe ser el 18% de la base (o 10% en restaurantes y hoteles MYPE) | Error |
| Base + IGV + otros cargos − descuentos debe dar el total | Error |
| La serie de una factura empieza con F; la de una boleta, con B (las físicas usan números) | Error |
| Una factura debe tener el RUC del cliente | Error |
| Una boleta de más de S/ 700 debe tener DNI y nombre del cliente | Advertencia |
| La suma de los ítems debe cuadrar con el total | Advertencia |
| Si hay QR y sus datos no coinciden con lo que leyó la IA, manda el QR | Advertencia |

Si hay al menos un **error**, el resultado sale con `needs_review: true`.

---

## 6. Tecnologías

| Tecnología | Para qué |
|---|---|
| **Python** | Lenguaje del proyecto |
| **uv** | Manejar dependencias y el entorno virtual |
| **FastAPI** | La API (el endpoint que recibe la imagen) |
| **Pydantic** | Definir la forma del JSON y validar tipos (viene con FastAPI) |
| **pydantic-settings** | Leer la configuración y la API key desde el archivo `.env` |
| **Gemini** (`google-genai`) | Modelo de IA que lee la imagen. Diseñado para poder cambiarlo por Claude u OpenAI |
| **OpenCV** | Leer el código QR |
| **Pillow** | Enderezar y reducir el tamaño de la imagen |
| **pytest** | Pruebas automáticas |
| **Docker** | Empaquetar el servicio para ejecutarlo en cualquier lugar |

---

## 7. Cómo se medirá la calidad

- Se reunirán **30 a 50 boletas reales** (fotos propias en condiciones reales, boletas de la empresa con permiso, y algunas de prueba).
- Para cada una se anotarán a mano los **datos correctos**.
- Un script comparará lo que devuelve el sistema con los datos correctos y mostrará:
  - **Porcentaje de aciertos por campo** (RUC, total, IGV, fecha…)
  - **Costo** por boleta
  - **Tiempo** de respuesta
- Esos resultados irán en el README del proyecto.

---

## 8. Estado actual

- [x] Proyecto creado con FastAPI y endpoint `/health`
- [x] Formato de los datos (esquema)
- [ ] Validaciones
- [ ] Lectura del QR
- [ ] Preparación de la imagen
- [ ] Conexión con Gemini
- [ ] Endpoint `/receipts/extract` completo
- [ ] Medición de calidad (evals)
- [ ] Docker y README
