# Code context — fixed revision


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
 199  		And("task_id = ?", tc.TaskID).
 200  		NoAutoCondition().
 201  		Get(tc)
 202  	if err != nil {
 203  		return err
 204  	}
 205  	if !exists {
 206  		return ErrTaskCommentDoesNotExist{
 207  			ID:     tc.ID,
 208  			TaskID: tc.TaskID,
 209  		}
 210  	}
 211  
 212  	return nil
 213  }
 214  
 215  // ReadOne handles getting a single comment
 216  // @Summary Remove a task comment
 217  // @Description Remove a task comment. The user doing this need to have at least read access to the task this comment belongs to.
 218  // @tags task
 219  // @Accept json
 220  // @Produce json
 221  // @Security JWTKeyAuth
 222  // @Param taskID path int true "Task ID"
 223  // @Param commentID path int true "Comment ID"
 224  // @Success 200 {object} models.TaskComment "The task comment object."
 225  // @Failure 400 {object} web.HTTPError "Invalid task comment object provided."
 226  // @Failure 404 {object} web.HTTPError "The task comment was not found."
 227  // @Failure 500 {object} models.Message "Internal error"
 228  // @Router /tasks/{taskID}/comments/{commentID} [get]
 229  func (tc *TaskComment) ReadOne(s *xorm.Session, _ web.Auth) (err error) {
 230  	err = getTaskCommentSimple(s, tc)
 231  	if err != nil {
 232  		return err
 233  	}
 234  
 235  	// Get the author
 236  	author := &user.User{}
 237  	_, err = s.
 238  		Where("id = ?", tc.AuthorID).
 239  		Get(author)
 240  	tc.Author = author
 241  	return
 242  }
 243  
 244  // ReadAll returns all comments for a task
 245  // @Summary Get all task comments
 246  // @Description Get all task comments. The user doing this need to have at least read access to the task.
 247  // @tags task
 248  // @Accept json
 249  // @Produce json
 250  // @Security JWTKeyAuth
 251  // @Param taskID path int true "Task ID"
 252  // @Param order_by query string false "Sort order. Can be 'asc' for ascending or 'desc' for descending. Defaults to 'asc'."
 253  // @Success 200 {array} models.TaskComment "The array with all task comments"
 254  // @Failure 500 {object} models.Message "Internal error"
```
