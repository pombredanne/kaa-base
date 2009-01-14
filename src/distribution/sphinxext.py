# No comments in here yet, because this code is repulsive.

import re
from sphinx.util.compat import make_admonition
from sphinx.ext.autodoc import prepare_docstring
import sphinx.addnodes

from docutils.parsers.rst import directives
from docutils import nodes
from docutils.statemachine import ViewList
from docutils.parsers.rst import directives

from kaa.notifier.object import get_all_signals


DELIM = u'xyzzy' * 10


class kaatable(nodes.paragraph):
    pass

class kaasection(nodes.paragraph):
    pass


def get_signals(cls, inherited, add, remove):
    if inherited:
        signals = get_all_signals(cls)
    else:
        signals = getattr(cls, '__kaasignals__', {}).copy()
        if add:
            all = get_all_signals(cls)
            for key in add:
                signals[key] = all[key]

    for key in remove:
        del signals[key]

    for key, val in signals.items():
        yield key, val


def get_members(cls, inherited, add, remove, pre_filter, post_filter):
    if inherited:
        keys = dir(cls)
    else:
        keys = cls.__dict__.keys()

    keys = set([ name for name in keys if pre_filter(name, getattr(cls, name)) ])
    keys.update(set(add))
    keys = keys.difference(set(remove))
    keys = [ name for name in keys if post_filter(name, getattr(cls, name)) ]
    
    for name in sorted(keys):
        yield name, getattr(cls, name)

def get_methods(cls, inherited=False, add=[], remove=[]):
    return get_members(cls, inherited, add, remove,
                       lambda name, attr: not name.startswith('_'),
                       lambda name, attr: callable(attr))

def get_properties(cls, inherited=False, add=[], remove=[]):
    return get_members(cls, inherited, add, remove,
                       lambda name, attr: not name.startswith('_'),
                       lambda name, attr: isinstance(attr, property))

def get_first_line(docstr):
    if not docstr:
        return ''
    docstr = docstr.lstrip('\n')
    prefix = docstr[:docstr.index(docstr.strip())]
    lines = [ re.sub(r'^%s' % prefix, '', s).rstrip() for s in docstr.split('\n') ]
    if '' in lines:
        lines = lines[:lines.index('')]
    return ' '.join(lines)


def get_class(fullname):
    mod, clsname = fullname.rsplit('.', 1)
    cls = getattr(__import__(mod), clsname)
    return cls, clsname

def normalize_class_name(mod, name):
    for i in reversed(range(mod.count('.')+1)):
        fullname = '%s.%s' % (mod.rsplit('.', i)[0], name)
        try:
            get_class(fullname)
            return fullname
        except (ImportError, AttributeError):
            pass
    return '%s.%s' % (mod, name)
    

def tree(list, cls, level=0):
    name = normalize_class_name(cls.__module__, cls.__name__)
    if level > 0:
        name = ':class:`%s`' % name
    list.append('%d %s' % (level, name), '')
    for c in cls.__bases__:
        if c != object:
            tree(list, c, level+1)


def synopsis_directive(name, arguments, options, content, lineno,
                       content_offset, block_text, state, state_machine):
    inherited_signals = 'inherited-signals' in options
    add_signals = options.get('add-signals', [])
    remove_signals = options.get('remove-signals', [])
    inherited_members = 'inherited-members' in options
    add_members = options.get('add-members', [])
    remove_members = options.get('remove-members', [])

    cls, clsname = get_class(arguments[0])

    list = ViewList()
    table = kaatable()
    table.clsname = arguments[0]

    def append(v1, v2):
        list.append(DELIM, '')
        list.append(v1, '')
        list.append(DELIM, '')
        list.append(v2, '')
        list.append(DELIM, '')

    list.append(DELIM, '')
    tree(list, cls)
    list.append(DELIM, '')

    for key, val in get_signals(cls, inherited_signals, add_signals, remove_signals):
        append(key, get_first_line(val))
    append('', '')

    for name, prop in get_properties(cls, inherited_members, add_members, remove_members):
        append(name, get_first_line(prop.__doc__))
    append('', '')

    for name, method in get_methods(cls, inherited_members, add_members, remove_members):
        append(name, get_first_line(method.__doc__))
    append('', '')

    table.append(nodes.Text(DELIM))
    state.nested_parse(list, 0, table)
    return [table]


def kaatable_visit(self, node):
    return

def kaatable_depart(self, node):
    # This is where things get ugly.  Conceptually I'm fairly sure this entire
    # approach (of rewriting the body in the depart handler) is completely
    # wrong, but I can't figure out the proper way to do it.

    idx = self.body.index(DELIM)
    html = ''.join(self.body[idx+2:])
    del self.body[idx:]
    signals, properties, methods = [], [], []
    all = [signals, properties, methods]

    m = re.search(r'(%s.*?%s)' % (DELIM, DELIM), html, re.S)
    tree = m.group(1)
    html = html[len(tree):]
    tree = tree[len(DELIM):-len(DELIM)]

    for name, desc in re.findall(r'%s(.*?)%s(.*?)%s' % (DELIM, DELIM, DELIM), html, re.S):
        if name == desc == '</p>\n<p>':
            all.pop(0)
        else:
            all[0].append((name.strip(), desc.strip()))
 

    link = lambda name, display: '<a title="%s.%s" class="reference internal" href="#%s.%s">%s</a>' % \
                                 (node.clsname, name, node.clsname, name, display)
    methods_filter = lambda name: link(name, name) + '()'
    properties_filter = lambda name: link(name, name)
    signals_filter = lambda name: link('signals.%s' % name, name)


    self.body.append('<h4>Synopsis</h4>')
    self.body.append('<b>Hierarchy Tree (Inverted)</b>')
    self.body.append('<p class="hierarchy">')
    for line in tree.split('\n'):
        if not line:
            continue
        level, clsname = line.split(' ', 1)
        if level == '0':
            clsname = '<tt class="xref docutils literal current">%s</tt>' % clsname
        self.body.append('%s+-- %s<br />' % ('&nbsp;' * 3 * int(level), clsname))
    self.body.append('</p>')



    for what in ('methods', 'properties', 'signals'):
        list = locals()[what]
        filter = locals()['%s_filter' % what]
        self.body.append('<b>%s</b>' % what.title())
        if not list:
            self.body.append('<p>This class has no %s.</p>' % what)
        else:
            self.body.append('<table class="kaa synopsis %s">' % what)
            for name, desc in list:
                self.body.append('<tr><th>%s</th><td>%s</td></tr>' % (filter(name), desc))
            self.body.append('</table>')



def auto_directive(name, arguments, options, content, lineno,
                       content_offset, block_text, state, state_machine):
    inherited_signals = 'inherited-signals' in options
    add_signals = options.get('add-signals', [])
    remove_signals = options.get('remove-signals', [])
    inherited_members = 'inherited-members' in options
    add_members = options.get('add-members', [])
    remove_members = options.get('remove-members', [])

    cls, clsname = get_class(arguments[0])

    list = ViewList()
    section = kaasection()
    section.title = name[4:].title()

    if name == 'automethods':
        for attrname, method in get_methods(cls, inherited_members, add_members, remove_members):
            list.append(u'.. automethod:: %s.%s' % (arguments[0], attrname), '')
    elif name == 'autoproperties':
        # TODO: indicate somewhere if property is read/write.
        for attrname, prop in get_properties(cls, inherited_members, add_members, remove_members):
            list.append(u'.. autoattribute:: %s.%s' % (arguments[0], attrname), '')
    elif name == 'autosignals':
        for attrname, docstr in get_signals(cls, inherited_signals, add_signals, remove_signals):
            list.append(u'.. attribute:: %s' %  attrname, '')
            list.append(u'', '')
            for line in docstr.split('\n'):
                list.append(line, '')
            list.append(u'', '')

    if not len(list):
        return []

    state.nested_parse(list, 0, section)
    if name == 'autosignals':
        # For signals, rewrite the id for each attribute from kaa.Foo.bar to
        # kaa.Foo.signals.bar (to prevent conflicts from actual attributes
        # called bar).
        for child in section.children:
            if isinstance(child, sphinx.addnodes.desc) and child.children:
                signame = str(child.children[0][0].children[0])
                child.children[0]['ids'] = [u'%s.signals.%s' % (arguments[0], signame)]

    return [section]


def kaasection_visit(self, node):
    self.body.append('<h4>%s</h4>' % node.title)

def kaasection_depart(self, node):
    return

def members_option(arg):
    if arg is None:
        return ['__all__']
    return [ x.strip() for x in arg.split(',') ]


def setup(app):
    synopsis_options = {
        'inherited-members': directives.flag,
        'inherited-signals': directives.flag,
        'add-members': members_option,
        'remove-members': members_option,
        'add-signals': members_option,
        'remove-signals': members_option,
    }

    members_options = {
        'inherited-members': directives.flag,
        'add-members': members_option,
        'remove-members': members_option,
    }

    signals_options = {
        'inherited-signals': directives.flag,
        'add-signals': members_option,
        'remove-signals': members_option,
    }

    app.add_node(kaatable, html=(kaatable_visit, kaatable_depart))
    app.add_node(kaasection, html=(kaasection_visit, kaasection_depart))
    app.add_directive('autosynopsis', synopsis_directive, 1, (0, 1, 1), **synopsis_options)
    app.add_directive('autoproperties', auto_directive, 1, (0, 1, 1), **members_options)
    app.add_directive('automethods', auto_directive, 1, (0, 1, 1), **members_options)
    app.add_directive('autosignals', auto_directive, 1, (0, 1, 1), **signals_options)