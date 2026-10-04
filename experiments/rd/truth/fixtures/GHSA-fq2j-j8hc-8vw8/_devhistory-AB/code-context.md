# Code context (neutral revisions) — adjudication for this fixture


## revision_A — kernel/api/lute.go (lines 135-204)

```go
 135  						p.AppendChild(c)
 136  					}
 137  					tree.Root.FirstChild.Unlink()
 138  					tree.Root.PrependChild(p)
 139  				}
 140  			}
 141  		}
 142  	}
 143  
 144  	if util.ContainerStd == model.Conf.System.Container {
 145  		// 处理本地资源文件复制
 146  		ast.Walk(tree.Root, func(n *ast.Node, entering bool) ast.WalkStatus {
 147  			if !entering || ast.NodeLinkDest != n.Type {
 148  				return ast.WalkContinue
 149  			}
 150  
 151  			if "" == n.TokensStr() {
 152  				return ast.WalkContinue
 153  			}
 154  
 155  			localPath := n.TokensStr()
 156  			if strings.HasPrefix(localPath, "http") {
 157  				return ast.WalkContinue
 158  			}
 159  
 160  			localPath = strings.TrimPrefix(localPath, "file://")
 161  			if gulu.OS.IsWindows() {
 162  				localPath = strings.TrimPrefix(localPath, "/")
 163  			}
 164  
 165  			unescaped, _ := url.PathUnescape(localPath)
 166  			if unescaped != localPath {
 167  				// `Convert network images/assets to local` supports URL-encoded local file names https://github.com/siyuan-note/siyuan/issues/9929
 168  				localPath = unescaped
 169  			}
 170  
 171  			if !filepath.IsAbs(localPath) {
 172  				// Kernel crash when copy-pasting from some browsers https://github.com/siyuan-note/siyuan/issues/9203
 173  				return ast.WalkContinue
 174  			}
 175  			if !gulu.File.IsExist(localPath) {
 176  				return ast.WalkContinue
 177  			}
 178  
 179  			if util.IsSensitivePath(localPath) {
 180  				logging.LogWarnf("skip copying asset [%s] due to sensitive path", localPath)
 181  				return ast.WalkContinue
 182  			}
 183  
 184  			name := filepath.Base(localPath)
 185  			ext := filepath.Ext(name)
 186  			name = name[0 : len(name)-len(ext)]
 187  			name = name + "-" + ast.NewNodeID() + ext
 188  			targetPath := filepath.Join(util.DataDir, "assets", name)
 189  			if err := filelock.Copy(localPath, targetPath); err != nil {
 190  				logging.LogErrorf("copy asset from [%s] to [%s] failed: %s", localPath, targetPath, err)
 191  				return ast.WalkStop
 192  			}
 193  			n.Tokens = gulu.Str.ToBytes("assets/" + name)
 194  			return ast.WalkContinue
 195  		})
 196  	}
 197  
 198  	parse.TextMarks2Inlines(tree) // 先将 TextMark 转换为 Inlines https://github.com/siyuan-note/siyuan/issues/13056
 199  	parse.NestedInlines2FlattedSpansHybrid(tree, false)
 200  
 201  	md, err := lute.FormatNodeSync(tree.Root, luteEngine.ParseOptions, luteEngine.RenderOptions)
 202  	if nil != err {
 203  		ret.Data = "Failed to convert"
 204  		return
```

## revision_B — kernel/api/lute.go (lines 135-204)

```go
 135  						p.AppendChild(c)
 136  					}
 137  					tree.Root.FirstChild.Unlink()
 138  					tree.Root.PrependChild(p)
 139  				}
 140  			}
 141  		}
 142  	}
 143  
 144  	if util.ContainerStd == model.Conf.System.Container {
 145  		// 处理本地资源文件复制
 146  		ast.Walk(tree.Root, func(n *ast.Node, entering bool) ast.WalkStatus {
 147  			if !entering || ast.NodeLinkDest != n.Type {
 148  				return ast.WalkContinue
 149  			}
 150  
 151  			if "" == n.TokensStr() {
 152  				return ast.WalkContinue
 153  			}
 154  
 155  			localPath := n.TokensStr()
 156  			if strings.HasPrefix(localPath, "http") {
 157  				return ast.WalkContinue
 158  			}
 159  
 160  			localPath = strings.TrimPrefix(localPath, "file://")
 161  			if gulu.OS.IsWindows() {
 162  				localPath = strings.TrimPrefix(localPath, "/")
 163  			}
 164  
 165  			unescaped, _ := url.PathUnescape(localPath)
 166  			if unescaped != localPath {
 167  				// `Convert network images/assets to local` supports URL-encoded local file names https://github.com/siyuan-note/siyuan/issues/9929
 168  				localPath = unescaped
 169  			}
 170  
 171  			if !filepath.IsAbs(localPath) {
 172  				// Kernel crash when copy-pasting from some browsers https://github.com/siyuan-note/siyuan/issues/9203
 173  				return ast.WalkContinue
 174  			}
 175  			if !gulu.File.IsExist(localPath) {
 176  				return ast.WalkContinue
 177  			}
 178  
 179  			name := filepath.Base(localPath)
 180  			ext := filepath.Ext(name)
 181  			name = name[0 : len(name)-len(ext)]
 182  			name = name + "-" + ast.NewNodeID() + ext
 183  			targetPath := filepath.Join(util.DataDir, "assets", name)
 184  			if err := filelock.Copy(localPath, targetPath); err != nil {
 185  				logging.LogErrorf("copy asset from [%s] to [%s] failed: %s", localPath, targetPath, err)
 186  				return ast.WalkStop
 187  			}
 188  			n.Tokens = gulu.Str.ToBytes("assets/" + name)
 189  			return ast.WalkContinue
 190  		})
 191  	}
 192  
 193  	parse.TextMarks2Inlines(tree) // 先将 TextMark 转换为 Inlines https://github.com/siyuan-note/siyuan/issues/13056
 194  	parse.NestedInlines2FlattedSpansHybrid(tree, false)
 195  
 196  	md, err := lute.FormatNodeSync(tree.Root, luteEngine.ParseOptions, luteEngine.RenderOptions)
 197  	if nil != err {
 198  		ret.Data = "Failed to convert"
 199  		return
 200  	}
 201  
 202  	tree = parse.Parse("", []byte(md), luteEngine.ParseOptions)
 203  	renderer := render.NewProtyleRenderer(tree, luteEngine.RenderOptions, luteEngine.ParseOptions)
 204  	output := renderer.Render()
```
