# Receipt Extractor

## 1. Qué es

Un servicio (API) que recibe la **imagen o PDF de un comprobante de compra** (boleta, factura, ticket, pedido online) **de cualquier país** y devuelve sus **datos en formato JSON**.

Es un servicio de una sola responsabilidad: **extraer bien los datos**. Lo que se haga después con ese JSON (guardarlo, exportarlo a Excel, usarlo en una rendición de cuentas) lo decide el sistema que lo consuma.

```
Imagen o PDF  ──►  POST /receipts/extract  ──►  JSON con los datos
```

Ejemplos de comprobantes que debe soportar: una boleta de supermercado en Perú, una factura de un proveedor, un ticket de restaurante, un pedido de Amazon, Temu o AliExpress.

---

## 2. Qué hace

- **Recibe una imagen** (JPG, PNG) **o un PDF**.
- **Prepara el archivo** antes de enviarlo: endereza la imagen, reduce su tamaño para gastar menos y convierte el PDF en imágenes.
- **Extrae los datos** con un modelo de IA con visión (Gemini al inicio). El diseño permite cambiar de proveedor sin tocar el resto del sistema.
- **Detecta el país y la moneda** del comprobante.
- **Valida que los datos sean coherentes** entre sí (que los montos cuadren con el total).
- **Reintenta una vez** si la validación encuentra un error, indicándole a la IA qué no cuadró.
- **Avisa cuando algo no está bien** (`needs_review: true`) en vez de inventar datos. Si un campo no se puede leer, queda vacío (`null`).
- **Informa el costo** de cada extracción (tokens usados).

## 3. Qué NO hace

- No guarda los archivos.
- No guarda los datos (no tiene base de datos).
- No exporta a Excel ni CSV.
- No procesa lotes de muchos comprobantes a la vez.

Todo eso puede construirse después, en otro sistema que use este servicio.

---

## 4. Datos que devuelve

El esquema es **genérico**: usa conceptos que existen en comprobantes de cualquier país. Los nombres locales (IGV, IVA, VAT, Sales Tax; RUC, EIN, RFC) se guardan tal como aparecen impresos.

### Datos del comprobante

| Campo | Qué es |
|---|---|
| `document_type` | Tipo: factura (`invoice`), boleta o ticket (`receipt`), pedido online (`order`), nota de crédito (`credit_note`) u otro (`other`) |
| `document_number` | Identificador impreso: `B001-4521`, `INV-2041`, número de pedido de Amazon… |
| `issue_date` | Fecha de emisión |
| `country` | País de emisión, código ISO de 2 letras (`PE`, `US`, `CN`…) |
| `currency` | Moneda, código ISO de 3 letras (`PEN`, `USD`, `EUR`, `CNY`…) |
| `issuer` | Quien vende: nombre y número tributario (`tax_id`: RUC, VAT number, EIN…) |
| `customer` | Quien compra: nombre y número tributario o documento, si aparece |
| `items` | Detalle: descripción, cantidad, precio unitario, descuento y total de cada producto |
| `subtotal` | Monto antes de impuestos, descuentos y envío |
| `discount` | Descuentos totales |
| `shipping` | Costo de envío |
| `taxes` | Lista de impuestos, cada uno con su nombre, tasa y monto |
| `tip` | Propina |
| `total` | Monto final pagado o por pagar |
| `payment_method` | Forma de pago: efectivo (`cash`), tarjeta (`card`), transferencia (`transfer`) u otra (`other`) |

`issuer` y `customer` usan la misma estructura (`Party`): en facturación, cada participante de una transacción es una "parte".

Los impuestos son una **lista**, no un campo fijo, porque cada país los llama distinto y un comprobante puede tener varios a la vez (por ejemplo, en Perú: IGV + impuesto a las bolsas plásticas).

### Información de la extracción

| Campo | Qué es |
|---|---|
| `issues` | Lista de problemas encontrados, cada uno con el campo, el mensaje y si es error o advertencia |
| `needs_review` | `true` si hay algún error: una persona debería revisarlo |
| `usage` | Modelo usado y tokens consumidos |

### Ejemplo: boleta peruana

```json
{
  "receipt": {
    "document_type": "receipt",
    "document_number": "B001-4521",
    "issue_date": "2026-10-05",
    "country": "PE",
    "currency": "PEN",
    "issuer": { "name": "SUPERMERCADOS PERUANOS S.A.", "tax_id": "20100070970" },
    "customer": { "name": "JUAN PEREZ", "tax_id": "71234567" },
    "items": [
      { "description": "LECHE GLORIA 1L", "quantity": 2, "unit_price": 5.50, "discount": null, "total": 11.00 },
      { "description": "ACEITE PRIMOR 1L", "quantity": 1, "unit_price": 39.00, "discount": 5.00, "total": 34.00 }
    ],
    "subtotal": 38.14,
    "discount": 5.00,
    "shipping": null,
    "taxes": [{ "name": "IGV", "rate": 0.18, "amount": 6.86 }],
    "tip": null,
    "total": 45.00,
    "payment_method": "card"
  },
  "issues": [],
  "needs_review": false,
  "usage": { "model": "gemini-flash-latest", "input_tokens": 1850, "output_tokens": 420 }
}
```

### Ejemplo: pedido de Amazon

```json
{
  "receipt": {
    "document_type": "order",
    "document_number": "112-4589321-7765012",
    "issue_date": "2026-10-05",
    "country": "US",
    "currency": "USD",
    "issuer": { "name": "Amazon.com Services LLC", "tax_id": null },
    "customer": { "name": "Alex Huaracha", "tax_id": null },
    "items": [
      { "description": "USB-C Cable 2m", "quantity": 2, "unit_price": 9.99, "discount": null, "total": 19.98 }
    ],
    "subtotal": 19.98,
    "discount": null,
    "shipping": 5.99,
    "taxes": [{ "name": "Sales Tax", "rate": 0.07, "amount": 1.82 }],
    "tip": null,
    "total": 27.79,
    "payment_method": "card"
  },
  "issues": [],
  "needs_review": false,
  "usage": { "model": "gemini-flash-latest", "input_tokens": 1720, "output_tokens": 380 }
}
```

---

## 5. Cómo se detecta el país

1. Si quien llama al servicio lo indica (`POST /receipts/extract?country=PE`), se usa ese país y además se le pasa al modelo como contexto.
2. Si no, el modelo lo deduce de las pistas del comprobante: palabras como "RUC" o "IGV", la moneda (`S/`), la dirección, el idioma.
3. Si no hay pistas suficientes, `country` queda en `null`.

---

## 6. Reglas de validación

Las validaciones comprueban que los datos extraídos sean coherentes entre sí, para cualquier comprobante.

| Regla | Si no se cumple |
|---|---|
| Debe tener fecha, emisor y total | Error |
| Los montos cuadran con el total (el impuesto puede estar sumado o incluido en los precios; el descuento, restado al final o ya aplicado) | Error |
| En cada ítem: cantidad × precio unitario − descuento = total del ítem | Advertencia |
| La suma de los ítems cuadra con el subtotal o el total | Advertencia |
| La fecha no está en el futuro | Advertencia |
| `country` y `currency` tienen formato de código ISO | Advertencia |

Los montos se comparan con una pequeña tolerancia (±0.05), porque los comprobantes redondean a 2 decimales.

Si hay al menos un **error**, el resultado sale con `needs_review: true`.

---

## 7. Tecnologías

| Tecnología | Para qué |
|---|---|
| **Python** | Lenguaje del proyecto |
| **uv** | Manejar dependencias y el entorno virtual |
| **FastAPI** | La API (el endpoint que recibe el archivo) |
| **Pydantic** | Definir la forma del JSON y validar tipos (viene con FastAPI) |
| **pydantic-settings** | Leer la configuración y la API key desde el archivo `.env` |
| **Gemini** (`google-genai`) | Modelo de IA que lee el comprobante. Diseñado para poder cambiarlo por otro proveedor |
| **Pillow** | Enderezar y reducir el tamaño de la imagen |
| **PyMuPDF** | Convertir PDF en imágenes (y leer su texto, si lo tiene) |
| **pytest** | Pruebas automáticas |
| **Docker** | Empaquetar el servicio para ejecutarlo en cualquier lugar |

---

## 8. Cómo se medirá la calidad

- Se reunirán **30 a 50 comprobantes reales y variados**: boletas peruanas (fotos en condiciones reales: torcidas, con poca luz, arrugadas), facturas, tickets de restaurante y pedidos online (Amazon, Temu, AliExpress).
- Para cada uno se anotarán a mano los **datos correctos**.
- Un script comparará lo que devuelve el sistema con los datos correctos y mostrará:
  - **Porcentaje de aciertos por campo** (fecha, emisor, total, impuestos…)
  - **Costo** por comprobante
  - **Tiempo** de respuesta
- Con el mismo script se compararán **distintos enfoques** para responder con datos si un LLM general es la mejor opción:
  1. **Gemini** (LLM general con visión)
  2. **Azure Document Intelligence** (servicio especializado en recibos)
  3. **PaddleOCR + un LLM pequeño** (híbrido de código abierto)
- Los resultados irán en el README del proyecto.

---

## 9. Mejoras futuras (no ahora)

- Leer el código QR de los comprobantes electrónicos peruanos (SUNAT) para confirmar los datos sin gastar tokens.
- Reglas de validación para más países.
- Más proveedores de IA (Claude, OpenAI).

---

## 10. Estado actual

- [x] Proyecto creado con FastAPI y endpoint `/health`
- [x] Formato de los datos (esquema genérico)
- [x] Validaciones de coherencia
- [ ] Preparación del archivo (imagen y PDF)
- [ ] Conexión con Gemini
- [ ] Endpoint `/receipts/extract` completo
- [ ] Medición de calidad (evals) y comparación de enfoques
- [ ] Docker y README
