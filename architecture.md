# ZipNN – Projektarchitektur & Windows-Portierungsplan

## 1. Projektüberblick

**ZipNN** ist eine verlustfreie Kompressionsbibliothek für KI-Pipelines (speziell für Modellgewichte wie `float16`, `bfloat16`, `float32`). Sie erreicht hohe Kompressions- und Dekompressionsraten durch Byte-/Bit-Neuanordnung von Gleitkommazahlen, gefolgt von Entropy-Coding (Huffman/FSE).

- **Version**: 0.5.4  
- **Lizenz**: MIT  
- **Zielplattform**: Linux/macOS (primär), Windows (in Arbeit)  
- **PyPI**: https://pypi.org/pypi/zipnn/

---

## 2. Verzeichnisstruktur

```
zipnn/
??? csrc/                        # C-Quellcode der Python-Extension
?   ??? zipnn_core.c             # Haupt-Kompressionslogik (Multithreading)
?   ??? zipnn_core_module.c      # Python-Modulregistrierung (PyInit_zipnn_core)
?   ??? zipnn_core_functions.h   # Funktionsdeklarationen
?   ??? data_manipulation_dtype16.c/h  # Byte-Neuanordnung für 16-bit Typen
?   ??? data_manipulation_dtype32.c/h  # Byte-Neuanordnung für 32-bit Typen
?   ??? pthread_compat.h         # Windows-Shim für pthreads ? Win32 API
?   ??? time_compat.h            # Windows-Shim für gettimeofday ? GetSystemTimeAsFileTime
?
??? include/                     # Git-Submodule (externe Abhängigkeiten)
?   ??? FiniteStateEntropy/      # Cyan4973/FiniteStateEntropy – Huffman/FSE Encoder
?   ?   ??? lib/                 # fse_compress.c, fse_decompress.c, huf_*.c, hist.c, entropy_common.c
?   ??? zstd/                    # facebook/zstd – Zstandard (nur als Referenz, wird NICHT kompiliert)
?
??? zipnn/                       # Python-Paket
?   ??? zipnn.py                 # Hauptklasse ZipNN (1429 Zeilen)
?   ??? util_header.py           # Enums: EnumMethod, EnumFormat, EnumLossy; Header-Serialisierung
?   ??? util_torch.py            # TorchScript-Hilfsfunktionen (Lossy Compression)
?   ??? util_safetensors.py      # SafeTensors-Integration
?   ??? util_patch.py            # Multiprocessing-Patcher
?   ??? __init__.py              # Exportiert: ZipNN, zipnn_hf, zipnn_safetensors
?
??? scripts/                     # CLI-Hilfsskripte
?   ??? zipnn_compress_file.py
?   ??? zipnn_decompress_file.py
?   ??? zipnn_compress_path.py
?   ??? zipnn_decompress_path.py
?   ??? zipnn_compress_safetensors.py
?   ??? zipnn_decompress_safetensors.py
?   ??? zipnn_compress_file_delta.py
?   ??? zipnn_decompress_file_delta.py
?
??? tests/                       # Testsuiten
?   ??? simple_stress_tests.py
?   ??? test_decompress_throughput.py
?   ??? test_memory_leak.py
?   ??? test_one_model.py
?
??? examples/                    # Beispielskripte
??? additionalTools/             # ASimilarityCalculator.py
??? setup.py                     # Build-Skript (setuptools + Extension)
??? requirements.txt             # numpy>=1.17.0, safetensors>=0.4.0
??? simple_example.py            # Minimales Nutzungsbeispiel
```

---

## 3. Architektur & Datenfluss

### 3.1 Kompressionsablauf

```
Python-Input (bytes / torch.Tensor / numpy.ndarray)
        ?
        ?
ZipNN.compress()
        ?
        ?? [Lossy] zipnn_multiply_if_max_below()     ? TorchScript
        ?
        ?? Byte/Bit-Neuanordnung nach dtype:
        ?       dtype16: split_bytearray_dtype16()   ? C (data_manipulation_dtype16.c)
        ?       dtype32: split_bytearray_dtype32()   ? C (data_manipulation_dtype32.c)
        ?
        ?? py_zipnn_core()                           ? C-Extension (zipnn_core.c)
                ?
                ?? Chunks aufteilen
                ?? Multi-Thread Worker (pthread / Win32)
                ?       ?? HUF_compress() / FSE     ? FiniteStateEntropy (include/)
                ?? Threshold-Check (lohnt Kompression?)
                ?? Ergebnis: Header + CompChunkTypes + CumulativeSizes + komprimierte Daten
```

### 3.2 Dekompressionsablauf

```
Komprimiertes Byte-Objekt
        ?
        ?
ZipNN.decompress()
        ?
        ?? _retrieve_header()   ? Header-Parsing (util_header.py)
        ?
        ?? py_combine_dtype()   ? C-Extension (zipnn_core.c)
                ?
                ?? Multi-Thread Dekompression (HUF_decompress)
                ?? combine_buffers_dtype16/32()
                ?? Byte/Bit-Rücktransformation
```

### 3.3 Header-Format (32 Bytes)

Der Header enthält: Versionsnummer, Methode, Format, Byte-Reorder-Mode, Bit-Reorder-Mode, Dtype-Code, Chunk-Größe, Original-Länge, komprimierte Länge sowie optionale Extended-Header für Shape und Lossy-Parameter.

---

## 4. Externe Abhängigkeiten (Git-Submodule)

| Submodul | Repository | Zweck | Eingebunden als |
|---|---|---|---|
| `include/FiniteStateEntropy` | github.com/Cyan4973/FiniteStateEntropy | Huffman- und FSE-Entropy-Coding | C-Quellen direkt kompiliert via `setup.py` |
| `include/zstd` | github.com/facebook/zstd | Zstandard (optional, Fallback) | Wird **nicht** kompiliert; Python `zstandard`-Paket wird verwendet |

**Python-Abhängigkeiten** (`requirements.txt` / `setup.py`):
- `numpy >= 1.17.0`
- `safetensors >= 0.4.0`
- `torch >= 2.0.0` (optional, für Tensor-Unterstützung)
- `zstandard` (optional, für ZSTD-Methode)
- `lz4` (optional, für LZ4-Methode)

---

## 5. Kompressionsalgorithmen

| Methode | Implementierung | Verwendung |
|---|---|---|
| **HUFFMAN** (Standard) | `FiniteStateEntropy` C-Library | Standard, schnellste Option |
| **ZSTD** | Python `zstandard`-Paket | Alternativ, höhere Ratio |
| **LZ4** | Python `lz4`-Paket | Alternativ, sehr schnell |
| **SNAPPY** | Python `snappy`-Paket | Alternativ |
| **AUTO** | Wählt beste Methode | Default |

---

## 6. Windows-Status: Was bereits gemacht wurde

Jemand hat bereits folgende Windows-Anpassungen vorgenommen:

| Datei | Anpassung |
|---|---|
| `csrc/pthread_compat.h` | **Neu erstellt**: Emuliert pthreads API über `_beginthreadex` / Win32 `CRITICAL_SECTION` |
| `csrc/time_compat.h` | **Neu erstellt**: Emuliert `gettimeofday()` über `GetSystemTimeAsFileTime()` |
| `csrc/zipnn_core.c` | `#ifdef _WIN32` Guards für pthread- und time-Includes |
| `setup.py` | Windows-spezifische Compile-Flags (`/O2`, `/W3`), `Build_ext_win_amd64`-Klasse, Python311-Lib-Pfad hardcoded |

---

## 7. Aktueller Build-Status und Fehleranalyse

### 7.1 Build läuft durch – aber die Extension crasht beim Import

Der Build mit `python setup.py build_ext --inplace` **schließt ohne Compilerfehler ab**. Die `.pyd`-Datei `zipnn_core.cp311-win_amd64.pyd` wird erzeugt (x64, korrekt). Beim Import jedoch:

```
Windows fatal exception: access violation
? Exit Code: -1073741819 (= 0xC0000005 = STATUS_ACCESS_VIOLATION)
```

Der Absturz tritt auf bei `create_module` (DLL-Initialisierung), also beim Laden der Extension, **bevor** Python-Code läuft.

### 7.2 Wurzelursache: `PTHREAD_MUTEX_INITIALIZER` als statischer Initializer

**Das ist der kritische Bug:**

In `csrc/pthread_compat.h` ist `PTHREAD_MUTEX_INITIALIZER` als `{0}` definiert:
```c
#define PTHREAD_MUTEX_INITIALIZER {0}
```

In `csrc/zipnn_core.c` wird es so verwendet (in zwei Stellen, Zeile 484 und 1126):
```c
pthread_mutex_t next_chunk_mutex = PTHREAD_MUTEX_INITIALIZER;
```

Auf Windows ist `pthread_mutex_t` ein `CRITICAL_SECTION`. Eine `CRITICAL_SECTION` kann **nicht** mit `{0}` statisch initialisiert werden – sie muss mit `InitializeCriticalSection()` initialisiert werden. Das `{0}` erzeugt eine strukturell ungültige `CRITICAL_SECTION`, die beim ersten Zugriff crasht. Da diese Variablen als lokale Variablen in Funktionen deklariert werden (nicht global), wird die Initialisierung zur Laufzeit aufgerufen, was den Access Violation beim Modullade-Zeitpunkt verursacht, wenn die DLL-Initialisierungsroutine abläuft.

### 7.3 Weitere potenzielle Probleme

| Problem | Datei | Details |
|---|---|---|
| Hardcodierter Python-Pfad | `setup.py` | `/LIBPATH:C:\\Python311\\libs` – schlägt auf anderen Systemen fehl |
| `win32` vs. `win-amd64` Mismatch | `setup.py` | Build erzeugt `temp.win32-cpython-311` aber `lib.win32-cpython-311`, PYD aber als `win_amd64` |
| C4716-Warnings | `zipnn_core.c` Z.390, Z.880 | Thread-Funktionen ohne Return-Value (`pthread_exit` nicht als `noreturn` erkannt) |
| `struct timeval` | `time_compat.h` | Potenzieller Konflikt mit `winsock.h`-Definition |

---

## 8. Optionen für eine saubere Windows-Lösung

### Option A: C-Extension reparieren (Minimaler Aufwand)

**Was zu tun ist:**
1. `PTHREAD_MUTEX_INITIALIZER`-Verwendung ersetzen durch expliziten `pthread_mutex_init()` Aufruf
2. `setup.py` Python-Pfad dynamisch ermitteln
3. Build-Platform-Konsistenz sicherstellen

**Vorteile:**
- Minimaler Eingriff, bleibt kompatibel mit Linux/macOS
- Gleiche Codebasis

**Nachteile:**
- pthread-Shim ist fragil; spätere pthreads-Features könnten Probleme machen
- `setup.py`-Komplexität bleibt

**Aufwand:** ~2–4 Stunden

---

### Option B: C-Extension als reines Windows-Projekt mit CMake/MSVC

**Was zu tun ist:**
- `CMakeLists.txt` für die C-Extension erstellen
- pthreads-Shim durch natives Win32 API oder `std::thread` (C++) ersetzen
- `setup.py` verwendet `cmake` als Backend

**Vorteile:**
- Sauberere Build-Integration in Visual Studio
- Besseres Debugging möglich

**Nachteile:**
- Erfordert CMake-Setup
- Zwei Build-Systeme (CMake + setuptools) zu pflegen

**Aufwand:** ~1–2 Tage

---

### Option C: C-Extension in C++ mit `std::thread` (Plattform-neutral)

**Was zu tun ist:**
- `zipnn_core.c` ? `zipnn_core.cpp` umschreiben
- `pthread_compat.h` entfernen, `std::thread` + `std::mutex` verwenden
- Kompiliert nativ auf Windows (MSVC) und Linux (GCC/Clang) ohne Shim

**Vorteile:**
- Kein plattformspezifischer Shim nötig
- Moderne, wartbare Codebasis
- Vollständig in Visual Studio debugbar

**Nachteile:**
- Signifikanter Refactoring-Aufwand (~500–800 Zeilen betroffen)
- Python C-API bleibt C-style, mischt C/C++

**Aufwand:** ~3–5 Tage

---

### Option D: Neuimplementierung als C# / .NET-Bibliothek

**Was zu tun ist:**
- `ZipNN`-Logik in C# implementieren
- Python-Anbindung über `pythonnet` oder als eigenständige .NET-Bibliothek
- `FiniteStateEntropy` als P/Invoke-DLL oder in C# reimplementieren

**Vorteile:**
- Erstklassige Windows-Integration (Visual Studio, NuGet, .NET-Ökosystem)
- Einfaches Deployment (kein C-Compiler beim Nutzer nötig)
- Async/Task statt pthreads
- Einfache Tests mit xUnit/MSTest

**Nachteile:**
- Größter Aufwand, komplett neues Projekt
- Python-Kompatibilität erfordert `pythonnet`-Brücke
- `FiniteStateEntropy` müsste in C# reimplementiert oder per P/Invoke eingebunden werden
- Performance-Overhead durch managed/unmanaged Grenze

**Aufwand:** ~2–4 Wochen

---

## 9. Empfehlung

### Empfehlung: Option A jetzt, Option C mittelfristig

**Sofort (Option A) – Fix in ~2–4 Stunden:**

Den bestehenden Windows-Port durch Beheben des `PTHREAD_MUTEX_INITIALIZER`-Bugs zum Laufen bringen:

```c
// VORHER (crasht auf Windows):
pthread_mutex_t next_chunk_mutex = PTHREAD_MUTEX_INITIALIZER;

// NACHHER (korrekt für Windows UND Linux):
pthread_mutex_t next_chunk_mutex;
pthread_mutex_init(&next_chunk_mutex, NULL);
```

Das behebt den Access Violation. Zusätzlich muss der hardcodierte Python-Pfad in `setup.py` dynamisch gemacht werden.

**Mittelfristig (Option C) – Saubere Lösung:**

Wenn das Projekt dauerhaft auf Windows laufen soll und die C-Extension weiterentwickelt wird, lohnt es sich, die Thread-Verwaltung auf `std::thread`/`std::mutex` umzuschreiben. Das eliminiert den Shim komplett und macht den Code plattform-neutral.

**Option D (C#)** ist nur sinnvoll, wenn:
- das Projekt primär als Windows-Werkzeug positioniert wird (kein Linux/PyPI-Support mehr nötig)
- Python-Anbindung nicht erforderlich ist
- ein kompletter Neustart strategisch gewünscht ist

---

## 10. Konkreter Umsetzungsplan (Option A)

### Schritt 1: `csrc/pthread_compat.h` – `PTHREAD_MUTEX_INITIALIZER` entfernen

```c
// Zeile entfernen:
// #define PTHREAD_MUTEX_INITIALIZER {0}
// Stattdessen: immer pthread_mutex_init() verwenden
```

### Schritt 2: `csrc/zipnn_core.c` – Beide Verwendungen ersetzen (Z. 484, Z. 1126)

```c
// Ersetzen von:
pthread_mutex_t next_chunk_mutex = PTHREAD_MUTEX_INITIALIZER;
// Durch:
pthread_mutex_t next_chunk_mutex;
pthread_mutex_init(&next_chunk_mutex, NULL);
```

### Schritt 3: `setup.py` – Python-Pfad dynamisch ermitteln

```python
import sysconfig
python_lib_dir = sysconfig.get_config_var('LIBDIR') or os.path.join(sys.prefix, 'libs')
python_lib = f"python{sys.version_info.major}{sys.version_info.minor}.lib"
```

### Schritt 4: Build-Platform-Konsistenz

Die `Build_ext_win_amd64`-Klasse ist bereits vorhanden und setzt `plat_name = 'win-amd64'`. Prüfen ob `temp.win32` vs. `temp.win-amd64` ein Problem ist.

### Schritt 5: Verifizieren

```powershell
python setup.py build_ext --inplace
python -c "import zipnn_core; print('OK')"
python simple_example.py
```
