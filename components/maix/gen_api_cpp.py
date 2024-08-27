'''
    @brief Generate C++ code for MaixPy API
    @license Apache 2.0
    @author Neucrack@Sipeed
    @date 2023.10.23
'''

import os
import argparse
import time
import sys

def generate_api_cpp(api_tree, headers, out_path = None):
    content = '''
// This file is generated by MaixPy gen_api.py,
// !! DO NOT edit this file manually

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/complex.h>
#include <pybind11/functional.h>
#include <pybind11/chrono.h>

{}

#include "maixpy.hpp"


using namespace maix;
using namespace maix::peripheral;

namespace py = pybind11;


PYBIND11_MODULE(_maix, m) {{
    {}
}}
'''
    code = []
    maix = api_tree["members"]["maix"]
    code.append('m.doc() = "{}";'.format(maix["doc"]))
    def gen_members(members, _code, parent_var, parent_name, parent_type, parent_names):
        for k, v in members.items():
            if type(v["doc"]) == str:
                doc = v["doc"]
            else:
                doc = v.get("doc", {}).get("py_doc", "")
                if not doc:
                    doc = v["doc"].get("brief", "")
            doc = doc.replace("\n", "\\n").replace('"', '\\"')
            if v["type"] == "module":
                sub_m_name = "m_{}".format(k)
                _code.append('auto {} = {}.def_submodule("{}", "{}");'.format(sub_m_name, parent_var, k, doc))
                gen_members(v["members"], _code, sub_m_name, k, v["type"], parent_names + [k])
            elif v["type"] == "class":
                sub_obj_name = "class_{}_{}".format("_".join(parent_names), k)
                v_names = parent_names + [k]
                _code.append('auto {} = py::class_<{}>({}, "{}");'.format(sub_obj_name, "::".join(v_names), parent_var, k))
                gen_members(v["members"], _code, sub_obj_name, k, v["type"], parent_names + [k])
            elif v["type"] == "func":
                kwargs_str = ", ".join(['py::arg("{}") {}'.format(x[1], '= {}'.format(x[2]) if x[2] is not None else "") for x in v["args"]])
                if kwargs_str:
                    kwargs_str = ", " + kwargs_str
                if k == "__init__":
                    func_name = parent_name
                    _code.append('{}.def(py::init<{}>(){});'.format(parent_var, ", ".join([x[0] for x in v["args"]]), kwargs_str))
                elif k == "__iter__":
                    func_name = parent_name
                    _code.append('{}.def("__iter__", []({} &c){{return py::make_iterator(c.begin(), c.end());}}, py::keep_alive<0, 1>());'.format(parent_var, "::".join(parent_names)))
                elif k == "__del__":
                    raise Exception("not support __del__ yet")
                else:
                    func_name = v["name"]
                    # if parent_type == "class":
                    if v["ret_type"].endswith("&"):
                        ret_policy = "reference"
                    else:
                        ret_policy = "take_ownership"
                    _code.append('{}.def{}("{}", static_cast<{} ({})({})>({}{}), py::return_value_policy::{}, "{}"{});'.format(
                                parent_var, "_static" if v["static"] else "", k,
                                v["ret_type"],
                                "::".join(parent_names + ["*"]) if (parent_type == "class" and not v["static"]) else "*",
                                ", ".join([x[0] for x in v["args"]]),
                                "&{}::".format("::".join(parent_names)) if len(parent_names) > 0  else "", func_name,
                                ret_policy,
                                doc, kwargs_str))
                    # else:
                    #     _code.append('{}.def{}("{}", {}{}, "{}"{});'.format(parent_var, "_static" if v["static"] else "",k,
                    #                         "&{}::".format("::".join(parent_names)) if len(parent_names) > 0  else "", func_name,
                    #                         doc, kwargs_str))

            elif v["type"] == "var":
                if parent_type == "class":
                    v_names = parent_names + [k]
                    if v["readonly"]:
                        _code.append('{}.def_readonly{}("{}", &{});'.format(parent_var, "_static" if v["static"] else "", k, "::".join(v_names) ))
                    else:
                        _code.append('{}.def_readwrite{}("{}", &{});'.format(parent_var, "_static" if v["static"] else "", k, "::".join(v_names)))
                else:
                    _code.append('{}.attr("{}") = {};'.format(parent_var, k, "::".join(parent_names + [k])))
            elif v["type"] == "enum":
                _code.append('py::enum_<{}>({}, "{}")'.format("::".join(parent_names + [k]), parent_var, k))
                for enum_k, v, comment in v["values"]:
                    v_names = parent_names + [k, enum_k]
                    _code.append('    .value("{}", {})'.format(enum_k, "::".join(v_names)))
                _code.append(';')


    gen_members(maix["members"], code, parent_var="m", parent_name="maix", parent_type="module", parent_names=[])

    code = "\n    ".join(code)
    headers_final = []
    for h in headers:
        headers_final.append('#include "{}"'.format(os.path.basename(h)))
    header_str = "\n".join(headers_final)
    content = content.format(header_str, code)
    if out_path:
        if os.path.dirname(out_path):
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)
    return content

def sort_headers(headers):
    # read headers_priority.txt
    headers_priority = []
    priority_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "headers_priority.txt")
    with open(priority_file, "r", encoding="utf-8") as f:
        for line in f.readlines():
            line = line.strip()
            if line.startswith("#"):
                continue
            headers_priority.append(line)
    # sort headers
    headers = sorted(headers, key = lambda x: headers_priority.index(os.path.basename(x)) if os.path.basename(x) in headers_priority else len(headers_priority))
    return headers

if __name__ == "__main__":
    print("-- Generate MaixPy C/C++ API")
    parser = argparse.ArgumentParser(description='Generate MaixPy C/C++ API')
    parser.add_argument('--vars', type=str, default="", help="CMake global variables file")
    parser.add_argument('-o', '--output', type=str, default="", help="API wrapper output file")
    parser.add_argument('--sdk_path', type=str, default="", help="MaixPy SDK path")
    args = parser.parse_args()

    t = time.time()

    sys.path.insert(0, os.path.join(args.sdk_path, "tools"))
    from doc_tool.gen_api import get_headers_recursive, parse_api_from_header
    from doc_tool.gen_markdown import module_to_md

    # get header files
    headers = []
    if args.vars:
        with open(args.vars, "r", encoding="utf-8") as f:
            vars = json.load(f)
        for include_dir in vars["includes"]:
            headers += get_headers_recursive(include_dir)
    else: # add sdk_path/components all .h and .hpp header files, except 3rd_party components
        except_dirs = ["3rd_party"]
        curr_dir = os.path.dirname(os.path.abspath(__file__))
        project_components_dir = os.path.abspath(os.path.join(curr_dir, ".."))
        componets_dirs = [os.path.join(args.sdk_path, "components"), project_components_dir]
        for componets_dir in componets_dirs:
            for root, dirs, files in os.walk(componets_dir):
                ignored = False
                for except_dir in except_dirs:
                    if os.path.join(componets_dir, except_dir) in root:
                        ignored = True
                        break
                if ignored:
                    continue
                for name in files:
                    path = os.path.join(root, name)
                    if path.endswith(".h") or path.endswith(".hpp"):
                        headers.append(path)
    # check each header file to find MaixPy API
    api_tree = {}
    rm = []
    all_keys = {}

    headers = sort_headers(headers)

    for header in headers:
        api_tree, updated, keys = parse_api_from_header(header, api_tree, sdks = ["maixpy"])
        if not updated:
            rm.append(header)
        for h, ks in all_keys.items():
            for k in ks:
                if k in keys:
                    raise Exception("API {} multiple defined in {} and {}".format(k, h, header))
        all_keys[header] = keys

    for r in rm:
        headers.remove(r)

    # generate API cpp file
    content = generate_api_cpp(api_tree, headers)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(content)
    print("-- Generate MaixPy C/C++ API done")

