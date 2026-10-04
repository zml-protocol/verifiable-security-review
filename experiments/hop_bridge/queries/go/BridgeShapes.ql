/**
 * @name secreview bridge shapes (Go)
 * @description Every node a §14 Go bridge hop endpoint may name, by kind, plus one row per file.
 * @kind table
 * @id secreview/bridge-shapes-go
 */

import go
import BridgeCommon

from string kind, string file, int sl, int sc, int el
where
  exists(Definition d | startOf(d, file, sl, sc) and el = d.getLocation().getEndLine() and kind = "definition")
  or
  exists(ParameterNode p | startOf(p, file, sl, sc) and el = sl and kind = "parameter")
  or
  exists(RangeValue r | startOf(r, file, sl, sc) and el = sl and kind = "range_value")
  or
  exists(CallArgument a | startOf(a, file, sl, sc) and el = a.getLocation().getEndLine() and kind = "call_argument")
  or
  exists(File f | file = f.getRelativePath() and sl = 0 and sc = 0 and el = 0 and kind = "file")
select kind, file, sl, sc, el
