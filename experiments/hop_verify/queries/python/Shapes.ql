/**
 * @name secreview hop shapes (Python)
 * @description Every node a Python hop endpoint may name, by kind, plus one row per extracted file.
 * @kind table
 * @id secreview/hop-shapes-python
 */

import python
import HopCommon

from string kind, string file, int sl, int sc, int el
where
  exists(MethodCall c | startOf(c, file, sl, sc) and el = sl and kind = "method_call")
  or
  exists(AttributeMethodCall c | startOf(c, file, sl, sc) and el = sl and kind = "attribute_method_call")
  or
  exists(Function f | functionLines(f, file, sl, el) and sc = 1 and kind = "function_body")
  or
  exists(Function f | f.isMethod() and functionLines(f, file, sl, el) and sc = 1 and kind = "method_body")
  or
  exists(File f | f.fromSource() and file = f.getRelativePath() and sl = 0 and sc = 0 and el = 0 and kind = "file")
select kind, file, sl, sc, el
