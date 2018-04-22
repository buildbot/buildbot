from __future__ import print_function
import sys
import logging
import codecs
from optparse import OptionParser
from pyjade.utils import process
import os

def convert_file():
    support_compilers_list = ['django', 'jinja', 'underscore', 'mako', 'tornado', 'html']
    available_compilers = {}
    for i in support_compilers_list:
        try:
            compiler_class = __import__('pyjade.ext.%s' % i, fromlist=['pyjade']).Compiler
        except ImportError as e:
            logging.warning(e)
        else:
            available_compilers[i] = compiler_class

    usage = "usage: %prog [options] [file [output]]"
    parser = OptionParser(usage)
    parser.add_option("-o", "--output", dest="output",
                    help="Write output to FILE", metavar="FILE")
    # use a default compiler here to sidestep making a particular
    # compiler absolutely necessary (ex. django)
    default_compiler = sorted(available_compilers.keys())[0]
    parser.add_option("-c", "--compiler", dest="compiler",
                    choices=list(available_compilers.keys()),
                    default=default_compiler,
                    type="choice",
                    help=("COMPILER must be one of %s, default is %s" %
                          (', '.join(list(available_compilers.keys())), default_compiler)))
    parser.add_option("-e", "--ext", dest="extension",
                      help="Set import/extends default file extension",
                      metavar="FILE")

    options, args = parser.parse_args()

    file_output = options.output or (args[1] if len(args) > 1 else None)
    compiler = options.compiler

    if options.extension:
        extension = '.%s' % options.extension
    elif options.output:
        extension = os.path.splitext(options.output)[1]
    else:
        extension = None

    if compiler in available_compilers:
        import six
        if len(args) >= 1:
            template = codecs.open(args[0], 'r', encoding='utf-8').read()
        elif six.PY3:
            template = sys.stdin.read()
        else:
            template = codecs.getreader('utf-8')(sys.stdin).read()
        output = process(template, compiler=available_compilers[compiler],
                         staticAttrs=True, extension=extension)
        if file_output:
            outfile = codecs.open(file_output, 'w', encoding='utf-8')
            outfile.write(output)
        elif six.PY3:
            sys.stdout.write(output)
        else:
            codecs.getwriter('utf-8')(sys.stdout).write(output)
    else:
        raise Exception('You must have %s installed!' % compiler)

if __name__ == '__main__':
    convert_file()
