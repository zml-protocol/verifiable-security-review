/**
 * @name secreview hop shapes (Go)
 * @description Every node a Go hop endpoint may name, by kind, plus one row per extracted file.
 * @kind table
 * @id secreview/hop-shapes-go
 */

import go
import HopCommon

from string kind, string file, int sl, int sc, int el
where
  exists(Definition d | startOf(d, file, sl, sc) and el = d.getLocation().getEndLine() and kind = "definition")
  or
  exists(FieldStore s | startOf(s, file, sl, sc) and el = s.getLocation().getEndLine() and kind = "field_store")
  or
  exists(KeyedField k | startOf(k, file, sl, sc) and el = k.getLocation().getEndLine() and kind = "keyed_field")
  or
  exists(File f | file = f.getRelativePath() and sl = 0 and sc = 0 and el = 0 and kind = "file")
select kind, file, sl, sc, el
