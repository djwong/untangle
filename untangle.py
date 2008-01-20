#!/usr/bin/python

# Untangle game, ported to python and cairo
# Copyright (C) 2008 Darrick J. Wong

import gtk
import math
import sys
import random

def distance(x1, y1, x2, y2):
	"""Calculate the distance between two points."""
	return math.hypot(x2 - x1, y2 - y1)

class Vertex:
	def __init__(self, x, y):
		"""Create a vertex with specified coordinates."""
		self.x = x
		self.y = y

	def clamp(self):
		"""Clamp coordinates."""
		def clamp(n):
			"""Clamp value between 0 and 1."""
			if n < 0:
				return 0
			elif n > 1:
				return 1
			return n
		self.x = clamp(self.x)
		self.y = clamp(self.y)

	def __repr__(self):
		return "v: %f, %f" % (self.x, self.y)

class Edge:
	def __init__(self, v1, v2):
		"""Create an edge between two vertices."""
		self.v1 = v1
		self.v2 = v2
		self.collision = False

	def __repr__(self):
		return "%s -> %s" % (str(self.v1), str(self.v2))

VERTEX_RADIUS = 6
class App:
	def __init__(self, is_editor):
		"""Create program controller."""
		self.vertices = []
		self.edges = []
		self.window = gtk.Window()
		self.canvas = GameFace()
		self.drag_vertex = None
		self.keymap = {
			gtk.keysyms.Tab: self.tab_key_press,
			gtk.keysyms.Up: self.arrow_key_press,
			gtk.keysyms.Down: self.arrow_key_press,
			gtk.keysyms.Left: self.arrow_key_press,
			gtk.keysyms.Right: self.arrow_key_press,
			gtk.keysyms.q: self.q_key_press,
			gtk.keysyms.h: self.help_key_press,
			gtk.keysyms.r: self.r_key_press,
		}
		editor_keymap = {
			gtk.keysyms.n: self.n_key_press,
			gtk.keysyms.s: self.s_key_press,
			gtk.keysyms.l: self.l_key_press,
			gtk.keysyms.Delete: self.del_key_press,
		}
		self.is_editor = is_editor
		if self.is_editor:
			self.keymap.update(editor_keymap)
		self.level = 0
		self.last_loaded_file = None

	def pollinate(self):
		"""Create a default set of vertices/edges."""
		v1 = Vertex(0.2, 0.2)
		v2 = Vertex(0.8, 0.2)
		v3 = Vertex(0.8, 0.8)
		v4 = Vertex(0.2, 0.8)

		e1 = Edge(v1, v2)
		e2 = Edge(v2, v3)
		e3 = Edge(v3, v4)
		e4 = Edge(v4, v1)
		e5 = Edge(v1, v3)
		e6 = Edge(v2, v4)

		self.vertices = [v1, v2, v3, v4]
		self.edges = [e1, e2, e3, e4, e5, e6]
		self.drag_vertex = None
		assert self.check_sanity()

		self.find_collisions()

	def pollinate_2(self, num_vertices):
		"""Create some number of vertices and edges."""
		self.vertices = []
		for i in range(0, num_vertices):
			x = random.uniform(0, 1)
			y = random.uniform(0, 1)
			v = Vertex(x, y)
			self.vertices.append(v)

		self.edges = []
		for i in range(0, num_vertices):
			v1 = self.vertices[i]
			for j in range(i + 1, num_vertices):
				v2 = self.vertices[j]
				e = Edge(v1, v2)
				self.edges.append(e)
				if not self.is_solved():
					self.edges.remove(e)

		assert self.check_sanity()

	def randomize_vertices(self):
		"""Move vertices to random locations."""
		for vertex in self.vertices:
			vertex.x = random.uniform(0, 1)
			vertex.y = random.uniform(0, 1)

	def save(self, fname):
		"""Save the current game."""
		fp = file(fname, "w")
		fp.write("# Untangle file format: One statement per line.  Two kinds of statements:\n")
		fp.write("# v: $x_coord $y_coord    -> Create a vertex with x and y coordinates, 0 <= coord <= 1.\n")
		fp.write("# e: $vert1 $vert2        -> Create an edge between vertex #1 and #2 (0-based index)\n");
		fp.write("#                            Both vertices must already be declared.\n")
		for vertex in self.vertices:
			fp.write("v: %f, %f\n" % (vertex.x, vertex.y))
		for edge in self.edges:
			fp.write("e: %d, %d\n" % (self.vertices.index(edge.v1), self.vertices.index(edge.v2)))
		fp.close()

	def load(self, fname):
		"""Load a game."""
		fp = file(fname, "r")
		vertices = []
		edges = []
		for line in fp:
			if line.startswith("v:"):
				args = line.split(" ")
				state = 0
				for arg in args:
					if state == 0 and arg == "v:":
						state = state + 1
					elif state == 1:
						arg = arg.strip(", ")
						x = float(arg)
						state = state + 1
					elif state == 2:
						arg = arg.strip(", ")
						y = float(arg)
						state = state + 1
					elif state == 3:
						break;
				if state == 3:
					v = Vertex(x, y)
					vertices.append(v)
			elif line.startswith("e:"):
				args = line.split(" ")
				state = 0
				for arg in args:
					if state == 0 and arg == "e:":
						state = state + 1
					elif state == 1:
						arg = arg.strip(", ")
						x = int(arg)
						state = state + 1
					elif state == 2:
						arg = arg.strip(", ")
						y = int(arg)
						state = state + 1
					elif state == 3:
						break;
				if state == 3:
					e = Edge(vertices[x], vertices[y])
					edges.append(e)
		fp.close()
		self.vertices = vertices
		self.edges = edges
		self.drag_vertex = None
		if not self.check_sanity():
			self.vertices = []
			self.edges = []
		self.last_loaded_file = fname
		self.window.set_title("%s - Untangle" % fname)
		self.canvas.queue_draw()

	def check_sanity(self):
		"""Check for obvious errors."""
		known_edges = []
		for edge in self.edges:
			if (edge.v1, edge.v2) in known_edges:
				print "Error, multiple edges between two vertices."
				return False
			known_edges.append((edge.v1, edge.v2))
			known_edges.append((edge.v2, edge.v1))
		for vertex in self.vertices:
			vertex.clamp()
		return True

	def help_key_press(self, a, b):
		"""Print help."""
		print_game_help()
		print ""
		print_editor_help()

	def find_collisions(self):
		"""Figure out which lines intersect."""
		def is_between(a, x0, x1):
			"""Determine if a is between x0 and x1."""
			if a > max(x0, x1):
				return False
			if a < min(x0, x1):
				return False
			return True

		for edge in self.edges:
			edge.collision = False

		for e1 in self.edges:
			for e2 in self.edges:
				if e1 == e2:
					continue

				# Line segment collision detection formulae
				# shamelessly stolen from http://local.wasp.uwa.edu.au/~pbourke/geometry/lineline2d/
				numerator_a = (e2.v2.x - e2.v1.x)*(e1.v1.y - e2.v1.y) - (e2.v2.y - e2.v1.y)*(e1.v1.x - e2.v1.x)
				numerator_b = (e1.v2.x - e1.v1.x)*(e1.v1.y - e2.v1.y) - (e1.v2.y - e1.v1.y)*(e1.v1.x - e2.v1.x)
				denominator = (e2.v2.y - e2.v1.y)*(e1.v2.x - e1.v1.x) - (e2.v2.x - e2.v1.x)*(e1.v2.y - e1.v1.y)

				# Deal with two edges that have common vertices
				verts = set()
				for vert in [e1.v1, e1.v2, e2.v1, e2.v2]:
					verts.add((vert.x, vert.y))
				if len(verts) == 3:
					# Three vertices means they're attached to the same point...

					# ...but are they coincident?
					if numerator_a == 0 and numerator_b == 0 and denominator == 0:
						e1.collision = True
						e2.collision = True
					continue
				elif len(verts) == 2:
					# Coincident
					e1.collision = True
					e2.collision = True
					continue

				# Deal with all other lines
				# Coincident or parallel lines
				if denominator == 0:
					# Test for coincidence
					if numerator_a == 0 and numerator_b == 0:
						e1.collision = True
						e2.collision = True
						continue
					# Parallel
					continue

				ua = numerator_a / denominator
				ub = numerator_b / denominator

				# Intersection of line segments
				if ua > 0 and ua < 1 and ub > 0 and ub < 1:
					e1.collision = True
					e2.collision = True

	def is_solved(self):
		"""Determine if the puzzle is solved (i.e. no collisions)"""
		self.find_collisions()
		for edge in self.edges:
			if edge.collision:
				return False
		return True

	def run_gtk(self):
		"""Start GTK app."""
		self.canvas.draw_hook = self.draw
		self.canvas.press_hook = self.mouse_down
		self.canvas.release_hook = self.mouse_up
		self.canvas.move_hook = self.mouse_move
		self.window.resize(400, 400)
		self.window.add(self.canvas)
		self.window.connect("destroy", gtk.main_quit)
		self.window.connect("key_press_event", self.key_press)
		self.window.show_all()
		gtk.main()

	def draw(self, context, rect):
		"""Draw game elements."""
		global VERTEX_RADIUS
		self.find_collisions()

		# Draw outer box
		context.set_line_width(1)
		context.rectangle(rect.x, rect.y, rect.width, rect.height)
		context.set_source_rgb(0.8, 0.8, 1)
		context.fill_preserve()
		context.set_source_rgb(0, 0, 0)
		context.stroke()

		# Draw lines
		context.set_line_width(2)
		for edge in self.edges:
			x1 = rect.width * edge.v1.x + rect.x
			y1 = rect.height * edge.v1.y + rect.y
			x2 = rect.width * edge.v2.x + rect.x
			y2 = rect.height * edge.v2.y + rect.y
			context.move_to(x1, y1)
			context.line_to(x2, y2)
			if edge.collision:
				context.set_source_rgb(1, 0, 0)
			else:
				context.set_source_rgb(0, 0, 0)
			context.stroke()

		# Draw vertices
		for vertex in self.vertices:
			x = rect.width * vertex.x + rect.x
			y = rect.height * vertex.y + rect.y
			context.arc(x, y, VERTEX_RADIUS, 0, 2.0 * math.pi)
			context.set_source_rgb(1, 1, 1)
			context.fill_preserve()
			context.set_source_rgb(0, 0, 0)
			context.stroke()
			if vertex == self.drag_vertex:
				context.arc(x, y, VERTEX_RADIUS - 4, 0, 2.0 * math.pi)
				context.set_source_rgb(0, 0, 0)
				context.fill_preserve()
				context.stroke()

	def delete_edge(self, v1, v2):
		"""Delete edge between two vertices."""
		if v1 == None:
			return False
		elif v1 == v2:
			return False
		dead_edges = []
		for edge in self.edges:
			if (edge.v1 == v1 and edge.v2 == v2) \
			or (edge.v1 == v2 and edge.v2 == v1):
				dead_edges.append(edge)
		for edge in dead_edges:
			self.edges.remove(edge)
		return True

	def add_edge(self, v1, v2):
		"""Add edge between two vertices."""
		if v1 == None:
			return
		elif v1 == v2:
			return
		e = Edge(v1, v2)
		self.edges.append(e)

	def mouse_down(self, x, y, button):
		"""Figure out if we need to start a drag."""
		rect = self.canvas.game_rect
		for vertex in self.vertices:
			draw_x = rect.width * vertex.x + rect.x
			draw_y = rect.height * vertex.y + rect.y
			dist = distance(x, y, draw_x, draw_y)
			if dist >= VERTEX_RADIUS:
				continue
			if button == 1:
				self.drag_vertex = vertex
				self.canvas.queue_draw()
				return True
			elif button == 3 and self.is_editor:
				self.add_edge(self.drag_vertex, vertex)
				self.canvas.queue_draw()
				return False
			elif button == 2 and self.is_editor:
				self.delete_edge(self.drag_vertex, vertex)
				self.canvas.queue_draw()
				return False
		self.drag_vertex = None
		return False

	def win(self):
		"""Win the game."""
		print "Yay, you won!"
		self.level = self.level + 1
		try:
			self.load("game%d.txt" % self.level)
		except:
			print "No more levels!"
			gtk.main_quit()

	def mouse_up(self, x, y):
		"""End drag operation."""
		self.canvas.queue_draw()
		if not self.is_editor and self.is_solved():
			self.win()

	def mouse_move(self, x, y):
		"""Drag a vertex somewhere."""
		assert self.drag_vertex != None

		# Translate to game coordinates
		rect = self.canvas.game_rect
		game_x = float(x - rect.x) / rect.width;
		game_y = float(y - rect.y) / rect.height;

		# Update vertex location
		self.drag_vertex.x = game_x
		self.drag_vertex.y = game_y
		self.drag_vertex.clamp()
		self.canvas.queue_draw()

	def key_press(self, widget, event):
		"""Dispatch key presses."""
		if self.keymap.has_key(event.keyval):
			self.keymap[event.keyval](widget, event)

	def tab_key_press(self, widget, event):
		"""Handle tab keys."""
		if self.drag_vertex == None:
			self.drag_vertex = self.vertices[0]
		else:
			idx = self.vertices.index(self.drag_vertex)
			idx = idx + 1
			if idx >= len(self.vertices):
				idx = 0
			self.drag_vertex = self.vertices[idx]
		self.canvas.queue_draw()


	def arrow_key_press(self, widget, event):
		"""Handle arrow key press."""
		if self.drag_vertex == None:
			return
		if event.keyval == gtk.keysyms.Up:
			self.drag_vertex.y = self.drag_vertex.y - 0.01
		elif event.keyval == gtk.keysyms.Down:
			self.drag_vertex.y = self.drag_vertex.y + 0.01
		elif event.keyval == gtk.keysyms.Left:
			self.drag_vertex.x = self.drag_vertex.x - 0.01
		elif event.keyval == gtk.keysyms.Right:
			self.drag_vertex.x = self.drag_vertex.x + 0.01
		self.drag_vertex.clamp()
		self.canvas.queue_draw()

	def del_key_press(self, widget, event):
		"""Delete vertex."""
		if self.drag_vertex == None:
			return
		dead_edges = []
		for edge in self.edges:
			if edge.v1 == self.drag_vertex or edge.v2 == self.drag_vertex:
				dead_edges.append(edge)
		for edge in dead_edges:
			self.edges.remove(edge)
		self.vertices.remove(self.drag_vertex)
		self.drag_vertex = None
		self.canvas.queue_draw()

	def n_key_press(self, widget, event):
		"""Create new vertex."""
		v = Vertex(0.5, 0.5)
		self.vertices.append(v)
		self.drag_vertex = v
		self.canvas.queue_draw()

	def s_key_press(self, widget, event):
		"""Save game."""
		if self.last_loaded_file != None:
			fname = self.last_loaded_file
		else:
			fname = "game.txt"
		self.save(fname)
		print "Saved game to '%s'." % fname

	def l_key_press(self, widget, event):
		"""Load game."""
		self.load("game.txt")
		print "Loaded game from 'game.txt'."

	def r_key_press(self, widget, event):
		"""Shuffle vertices around the board."""
		self.randomize_vertices()
		self.canvas.queue_draw()

	def q_key_press(self, widget, event):
		"""Quit game."""
		gtk.main_quit()

class GameFace(gtk.DrawingArea):
	def __init__(self):
		"""Create custom GTK drawing area."""
		super(GameFace, self).__init__()		
		self.connect("expose_event", self.expose)
		self.add_events(gtk.gdk.EXPOSURE_MASK |
			gtk.gdk.LEAVE_NOTIFY_MASK |
			gtk.gdk.BUTTON_PRESS_MASK |
			gtk.gdk.BUTTON_RELEASE_MASK |
			gtk.gdk.POINTER_MOTION_MASK |
			gtk.gdk.KEY_PRESS_MASK |
			gtk.gdk.POINTER_MOTION_HINT_MASK)

		self.connect("button_press_event", self.button_press)
		self.connect("button_release_event", self.button_release)
		self.connect("motion_notify_event", self.mouse_move)
		self.is_dragging = False
		self.game_rect = gtk.gdk.Rectangle(0, 0, 1, 1)

		self.draw_hook = None
		self.press_hook = None
		self.release_hook = None
		self.move_hook = None

		random.seed()

	def button_press(self, widget, event):
		"""Dispatch button press event to controller and start drag if desired."""
		if event.type == gtk.gdk.BUTTON_PRESS:
			if self.press_hook != None:
				res = self.press_hook(event.x, event.y, event.button)
			else:
				res = False
			if res:
				self.is_dragging = True
				self.grab_add()

	def button_release(self, widget, event):
		"""Dispatch button release event to controller."""
		if event.button == 1 and event.type == gtk.gdk.BUTTON_RELEASE and self.is_dragging:
			self.release_hook(event.x, event.y)
			self.grab_remove()
			self.is_dragging = False

	def mouse_move(self, widget, event):
		"""Dispatch mouse movement events to controller."""
		pos = self.get_pointer()
		if self.is_dragging:
			self.move_hook(pos[0], pos[1])

	def expose(self, widget, event):
		"""Figure out canvas size and redraw."""
		context = widget.window.cairo_create()
		
		# set a clip region for the expose event
		context.rectangle(event.area.x, event.area.y,
				  event.area.width, event.area.height)
		context.clip()
		
		self.draw(context)
		
		return False
	
	def draw(self, context):
		"""Draw items."""
		if self.draw_hook != None:
			rect = self.get_allocation()
			rect.x = rect.x + 2
			rect.y = rect.y + 2
			rect.width = rect.width - 4
			rect.height = rect.height - 4
			if rect.width > rect.height:
				rect.x = rect.x + (rect.width - rect.height) / 2
				rect.width = rect.height
			elif rect.height > rect.width:
				rect.y = rect.y + (rect.height - rect.width) / 2
				rect.height = rect.width
			self.game_rect = rect
			self.draw_hook(context, rect)

def print_help():
	"""Print help."""
	print "Usage: %s [-e [gamefile]]" % sys.argv[0]
	print ""
	print "-e:         Invoke editor mode."
	print "gamefile:   Edit a specific game file."
	print ""
	print_game_help()
	print ""
	print_editor_help()

def print_game_help():
	print "Game play: Drag the vertices around until the figure"
	print "is disentangled, i.e. all the edges are black.  You can"
	print "also <tab> and arrow keys to navigate around.  Press 'h'"
	print "for help, 'r' to shuffle vertices, and 'q' to quit."

def print_editor_help():
	"""Print editor help."""
	print "Editor: 's' to save, 'n' to add a new edge, <Del> to delete"
	print "an edge, and 'l' to revert to saved game.  To add an edge"
	print "between vertices, select one vertex and right-click on the"
	print "other one.  To delete, do the same, but middle-click.  Game"
	print "play keys/mouse bindings are the same."

def main():
	"""Main routine."""
	editor = False
	file = "game0.txt"
	num_vertices = 4

	if len(sys.argv) > 1:
		if sys.argv[1] == "-e":
			editor = True
		else:
			print_help()
			return
	if len(sys.argv) > 2:
		if editor:
			file = sys.argv[2]
		else:
			print_help()
			return

	if file == "-n":
		if editor:
			if len(sys.argv) > 3:
				try:
					num_vertices = int(sys.argv[3])
					file = None
				except:
					print_help()
					return
			else:
				print_help()
				return
		else:
			print_help()
			return

	app = App(editor)
	try:
		app.load(file)
	except:
		app.pollinate_2(num_vertices)
	app.run_gtk()

if __name__ == "__main__":
	main()
