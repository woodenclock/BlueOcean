/*
 * Copyright (C) 2026 ROS-Industrial Consortium Asia Pacific
 * Advanced Remanufacturing and Technology Centre
 * A*STAR Research Entities (Co. Registration No. 199702110H)
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 */

#ifndef VDA5050_CORE_PY__MASTER_BINDINGS_HPP_
#define VDA5050_CORE_PY__MASTER_BINDINGS_HPP_

#include <pybind11/pybind11.h>

namespace vda5050_core_py {

/// Register the FMS-side `VDA5050Master` bindings onto the `_core` module.
/// Called from `PYBIND11_MODULE(_core, ...)` in bindings.cpp AFTER the
/// transport (`MqttClient`) type is registered, since `make()` takes a
/// `shared_ptr<MqttClientInterface>`.
void register_master_bindings(pybind11::module_& m);

}  // namespace vda5050_core_py

#endif  // VDA5050_CORE_PY__MASTER_BINDINGS_HPP_
