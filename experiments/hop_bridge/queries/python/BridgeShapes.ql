/**
 * @name secreview bridge shapes (Python)
 * @description Every node a §14 Python bridge hop endpoint may name, by kind, plus one row per file.
 * @kind table
 * @id secreview/bridge-shapes-python
 */

import python
import BridgeCommon

from string kind, string file, int sl, int sc, int el
where
  exists(Parameter p | startOf(p, file, sl, sc) and el = sl and kind = "parameter")
  or
  exists(Definition d | startOf(d, file, sl, sc) and el = d.getLocation().getEndLine() and kind = "definition")
  or
  exists(Call c | startOf(c, file, sl, sc) and el = sl and kind = "call")
  or
  exists(MethodCall c | startOf(c, file, sl, sc) and el = sl and kind = "method_call")
  or
  exists(AttributeMethodCall c | startOf(c, file, sl, sc) and el = sl and kind = "attribute_method_call")
  or
  exists(File f | f.fromSource() and file = f.getRelativePath() and sl = 0 and sc = 0 and el = 0 and kind = "file")
select kind, file, sl, sc, el
