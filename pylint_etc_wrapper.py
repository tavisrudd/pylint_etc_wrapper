#!/usr/bin/env python
"""Feed this script the path of a Python module and it will print out
any warnings from pylint, pyflakes, and pep8.py that haven't been
explicitly silenced. The default output format is compatible with
Emacs' flymake mode.

This is derived from the anonymous flymake wrapper at
http://www.emacswiki.org/emacs/PythonMode
I'd credit the author, if I knew who they were.

Here's how to use it in Emacs:
(setq pycodechecker "pylint_etc_wrapper.py")
(when (load "flymake" t)
  (load-library "flymake-cursor")
  (defun dss/flymake-pycodecheck-init ()
    (let* ((temp-file (flymake-init-create-temp-buffer-copy
                       'flymake-create-temp-inplace))
           (local-file (file-relative-name
                        temp-file
                        (file-name-directory buffer-file-name))))
      (list pycodechecker (list local-file))))
  (add-to-list 'flymake-allowed-file-name-masks
               '("\\.py\\'" dss/flymake-pycodecheck-init)))

And here are two little helpers for quickly silencing a warning message:

(defun dss/pylint-msgid-at-point ()
  (interactive)
  (let (msgid
        (line-no (line-number-at-pos)))
    (dolist (elem flymake-err-info msgid)
      (if (eq (car elem) line-no)
            (let ((err (car (second elem))))
              (setq msgid (second (split-string (flymake-ler-text err)))))))))

(defun dss/pylint-silence (msgid)
  "Add a special pylint comment to silence a particular warning."
  (interactive (list (read-from-minibuffer "msgid: " (dss/pylint-msgid-at-point))))
  (save-excursion
    (comment-dwim nil)
    (if (looking-at "pylint:")
        (progn (end-of-line)
               (insert ","))
        (insert "pylint: disable-msg="))
    (insert msgid)))

"""
# ' extra apostrophe to fix Emacs python-mode broken string matching

# Copyright (c) 2002-present, Damn Simple Solutions Ltd.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above
#       copyright notice, this list of conditions and the following
#       disclaimer in the documentation and/or other materials provided
#       with the distribution.
#     * Neither the name of the Damn Simple Solutions Ltd. nor the names
#       of its contributors may be used to endorse or promote products
#       derived from this software without specific prior written
#       permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import re
from optparse import OptionParser
from subprocess import Popen, PIPE

flymake_output_format = (
    "%(level)s %(error_type)s%(error_number)s:"
    "%(description)s at %(filename)s line %(line_number)s.")

comint_output_format = (
    "%(filename)s:%(line_number)s:"
    " %(level)s: %(error_type)s%(error_number)s"
    " %(description)s.")


class LintRunner(object):
    sane_default_ignore_codes = set([])
    command = None
    output_matcher = None
    output_format = flymake_output_format
    env = None
    _debug = False

    def __init__(self, ignore_codes=(),
                 use_sane_defaults=True,
                 output_format=None,
                 debug=False):
        self.ignore_codes = set(ignore_codes)
        self.use_sane_defaults = use_sane_defaults
        if output_format:
            self.output_format = output_format
        self._debug = debug

    @property
    def operative_ignore_codes(self):
        if self.use_sane_defaults:
            return self.ignore_codes.union(self.sane_default_ignore_codes)
        else:
            return self.ignore_codes

    @property
    def run_flags(self):
        return ()

    def fixup_data(self, line, data):
        if self.command:
            data['error_number'] = '%s %s'%(data.get('error_number','?'), self.command)
        return data

    def process_line(self, line):
        m = self.output_matcher.match(line)
        if m:
            fixed_data = dict.fromkeys(
                ('level', 'error_type', 'error_number', 'description'
                 , 'filename', 'line_number'), '')
            fixed_data.update(self.fixup_data(line, m.groupdict()))
            self._handle_output(line, fixed_data)

    def _handle_output(self, line, fixed_data):
        print self.output_format % fixed_data

    def run(self, filenames):
        args = [self.command]
        args.extend(self.run_flags)
        args.extend(filenames)
        if self._debug:
            print "DEBUG: command = ", ' '.join(args)
        process = Popen(args, stdout=PIPE, stderr=PIPE, env=self.env)
        for line in process.stdout:
            if self._debug:
                print self.command, 'STDOUT:', line
            self.process_line(line)
        for line in process.stderr:
            if self._debug:
                print self.command, 'STDERR:', line

            #print 'ERR: ', line
            self.process_line(line)


class PylintRunner(LintRunner):
    output_matcher = re.compile(
        r'(?P<filename>[^:]+):'
        r'(?P<line_number>\d+):'
        r'\s*\[(?P<error_type>[WECR])(?P<error_number>[0-9]+)\]'
        #r'\s*(?P<context>[^\]]+)\]'
        r'\s*(?P<description>.*)$')

    command = 'pylint'
    sane_default_ignore_codes = set([
        "C0103"  # Naming convention
        , "W0108"  # Lambda may not be necessary
        , "C0111"  # Missing Docstring
        , "W0142"  # Used * or ** magic
        , "C0202"  # classmethod should have cls as first arg
        , "C0301"  # long lines, handled separately by other tools
        , "C0322"  # Operator not preceded
        , "C0323"  # Operator not followed by a space
        , "E1002"  # Use super on old-style class
        , "W0141"  # used built in function map
        , "W0232"  # No __init__
        , "W0621"  # Redefining name 'x' from outer scope
                   # (is sually complaining about dynamic scope, which doesn't matter)
        , "W0702"  # No exception type(s) specified
        #, "I0011"  # Warning locally suppressed using disable-msg
        #, "I0012"  # Warning locally suppressed using disable-msg
        #, "W0511"  # FIXME/TODO
        #, "W0142"  # *args or **kwargs magic.
        , "R0904"  # Too many public methods
        , "R0902"  # Too many instance attributes
        , "R0903"  # Too few public methods
        , "R0201"  # Method could be a function
        , "R0913"  # Too many arguments
        , "R0921"  # Abstract class not referenced
        # stuff t doesn't handle well because of incomplete inference
        , "E1101"  # Instance of 'x' has no 'y' member
        , "E1102" # x is not callable
        , "E1103" # Class 'x' has no 'y' member
        , "E0611" # module does not contain variable
        ])

    def fixup_data(self, line, data):
        data = LintRunner.fixup_data(self, line, data)
        if data['error_type'].startswith('E'):
            data['level'] = 'ERROR'
        else:
            data['level'] = 'WARNING'
        return data

    @property
    def run_flags(self):
        return ('--output-format', 'parseable'
                , '--include-ids', 'y'
                , '--reports', 'n'
                , '--disable=' + ','.join(self.operative_ignore_codes))


class Pep8Runner(LintRunner):
    command = 'pep8.py'
    sane_default_ignore_codes = set([
        #'RW29', 'W391', 'W291', 'WO232', #
        #'E202', # E202 whitespace before ']' or ')'
        'E231' # E231 is mising whitespace after punc.
        , 'E301' # E301 is something about expecting blank lines
        , 'E302'
        , 'E501' # E501 line too long (covered by lineker-mode)
        , 'E701' # E701 multiple statements on one line (colon)
        , 'E113' # unexpected indentation i.e. bad syntax - is handled
                # by pyflakes
        ])
    output_matcher = re.compile(
        r'(?P<filename>[^:]+):'
        r'(?P<line_number>[^:]+):'
        r'[^:]+:'
        r' (?P<error_number>\w+) '
        r'(?P<description>.+)$')

    def fixup_data(self, line, data):
        data = LintRunner.fixup_data(self, line, data)
        if ('W' in data['error_number']
            or data['error_number'][1] in '2345'):
            data['level'] = 'WARNING'
        else:
            data['level'] = 'ERROR'

        return data

    @property
    def run_flags(self):
        return ('--repeat'
                , '--filename=*py'
                , '--ignore=%s'%','.join(self.operative_ignore_codes))


class PyflakesRunner(LintRunner):
    command = 'pyflakes'
    output_matcher = re.compile(
        r'(?P<filename>[^:]+):'
        r'(?P<line_number>[^:]+)\s*:'
        r'(?P<description>.+)$')
    ignore_redefinition_warnings = True

    def fixup_data(self, line, data):
        data = LintRunner.fixup_data(self, line, data)
        data['level'] = 'ERROR'
        return data

    def _handle_output(self, line, fixed_data):
        if self.ignore_redefinition_warnings and (
            'redefinition of unused' in fixed_data['description']
            or 'redefinition of function' in fixed_data['description']):

            return
        else:
            print self.output_format % fixed_data

################################################################################
checkers = {
    "pylint":PylintRunner
    , "pep8":Pep8Runner
    , "pyflakes":PyflakesRunner
    }
################################################################################

def main():
    usage = "usage: %prog [options] [PY_MODULE_OR_PACKAGE]..."
    parser = OptionParser(usage=usage)
    parser.add_option(
        "-c", "--comint_format",
        action="store_true",
        default=False,
        help=("Emacs comint compatible output format."
              " Flymake compatible is the default."))
    parser.add_option(
        "-i", "--ignore_codes",
        default="",
        help="comma separated list of error codes to ignore")
    parser.add_option(
        "-p", "--checker_progs",
        default="pylint,pyflakes",
        help=("comma separated list of the checker"
              " programs to run. default=pylint,pyflakes"))
    parser.add_option(
        "-d", "--debug",
        action="store_true",
        default=False,
        help=("show debug output"))
    options, filenames = parser.parse_args()
    #

    selected_checkers = [
        checkers[c]
        for c in options.checker_progs.strip().split(",")]

    output_format = (
        comint_output_format if options.comint_format else flymake_output_format)
    ignore_codes = (
        options.ignore_codes.split(",") if options.ignore_codes else [])

    for RunnerClass in selected_checkers:
        runner = RunnerClass(
            output_format=output_format,
            ignore_codes=ignore_codes,
            debug=options.debug)
        runner.run(filenames)

if __name__ == '__main__':
    main()
