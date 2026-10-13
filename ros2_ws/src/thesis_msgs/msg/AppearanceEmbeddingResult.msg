# Thesis-Code
# Purpose: Define the matching appearance result, provenance and explicit
# completion status.
# Author: Francisco Tavares
# Copyright (c) 2026 Francisco Carreira Tavares
# SPDX-License-Identifier: MIT
#
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.

# Correlates this result with one in-flight causal request.
uint64 request_id

# Backend contract echoed by the worker.
string backend_name
string embedding_space
uint32 dimension

# Host monotonic timestamp domain.
int64 started_ns
int64 completed_ns

# Exactly one result state is valid:
# succeeded=true  -> error is empty and embedding contains dimension values.
# succeeded=false -> error is non-empty and embedding is empty.
bool succeeded
float32[] embedding
string error
