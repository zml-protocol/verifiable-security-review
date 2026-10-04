# Code context — vuln revision


## pkg/models/task_comments.go (lines 179-254)

```go
 179  	if err != nil {
 180  		return err
 181  	}
 182  
 183  	task, err := GetTaskSimple(s, &Task{ID: tc.TaskID})
 184  	if err != nil {
 185  		return err
 186  	}
 187  
 188  	events.DispatchOnCommit(s, &TaskCommentUpdatedEvent{
 189  		Task:    &task,
 190  		Comment: tc,
 191  		Doer:    tc.Author,
 192  	})
 193  	return nil
 194  }
 195  
 196  func getTaskCommentSimple(s *xorm.Session, tc *TaskComment) error {
 197  	exists, err := s.
 198  		Where("id = ?", tc.ID).
 199  		NoAutoCondition().
 200  		Get(tc)
 201  	if err != nil {
 202  		return err
 203  	}
 204  	if !exists {
 205  		return ErrTaskCommentDoesNotExist{
 206  			ID:     tc.ID,
 207  			TaskID: tc.TaskID,
 208  		}
 209  	}
 210  
 211  	return nil
 212  }
 213  
 214  // ReadOne handles getting a single comment
 215  // @Summary Remove a task comment
 216  // @Description Remove a task comment. The user doing this need to have at least read access to the task this comment belongs to.
 217  // @tags task
 218  // @Accept json
 219  // @Produce json
 220  // @Security JWTKeyAuth
 221  // @Param taskID path int true "Task ID"
 222  // @Param commentID path int true "Comment ID"
 223  // @Success 200 {object} models.TaskComment "The task comment object."
 224  // @Failure 400 {object} web.HTTPError "Invalid task comment object provided."
 225  // @Failure 404 {object} web.HTTPError "The task comment was not found."
 226  // @Failure 500 {object} models.Message "Internal error"
 227  // @Router /tasks/{taskID}/comments/{commentID} [get]
 228  func (tc *TaskComment) ReadOne(s *xorm.Session, _ web.Auth) (err error) {
 229  	err = getTaskCommentSimple(s, tc)
 230  	if err != nil {
 231  		return err
 232  	}
 233  
 234  	// Get the author
 235  	author := &user.User{}
 236  	_, err = s.
 237  		Where("id = ?", tc.AuthorID).
 238  		Get(author)
 239  	tc.Author = author
 240  	return
 241  }
 242  
 243  // ReadAll returns all comments for a task
 244  // @Summary Get all task comments
 245  // @Description Get all task comments. The user doing this need to have at least read access to the task.
 246  // @tags task
 247  // @Accept json
 248  // @Produce json
 249  // @Security JWTKeyAuth
 250  // @Param taskID path int true "Task ID"
 251  // @Param order_by query string false "Sort order. Can be 'asc' for ascending or 'desc' for descending. Defaults to 'asc'."
 252  // @Success 200 {array} models.TaskComment "The array with all task comments"
 253  // @Failure 500 {object} models.Message "Internal error"
 254  // @Router /tasks/{taskID}/comments [get]
```
