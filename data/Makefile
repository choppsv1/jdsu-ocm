YMB=jdsu-ocm
YMODULES=$(YMB).yang

OBJDIR ?= ../build
YMD = $(OBJDIR)/$(YMB)-data
YMC = $(OBJDIR)/$(YMB)-config
TIDY = cat


all: $(OBJDIR) $(OBJDIR)/jdsu-ocm-config.sch $(OBJDIR)/jdsu-ocm-data.sch

clean:
	rm -f $(YMD).* $(YMC).*  $(JTOX)

$(OBJDIR):
	mkdir -p $(OBJDIR)

$(OBJDIR)/%-config.rng $(OBJDIR)/%-config.sch $(OBJDIR)/%-config.dsrl: %.yang
	yang2dsdl -t config -d $(OBJDIR) $<
#	yang2dsdl -t config -d $(OBJDIR) -b $(basename $<) $<

$(OBJDIR)/%-data.rng $(OBJDIR)/%-data.sch $(OBJDIR)/%-data.dsrl: %.yang
	yang2dsdl -t data -d $(OBJDIR)  $<
#	yang2dsdl -t data -d $(OBJDIR) -b $(basename $<) $<

#$(YMD).rng $(YMD).sch $(YMD).dsrl: $(YMODULES)
#	yang2dsdl -t data -d $(OBJDIR) -b $(YMB) $(YMODULES)


test-yang: $(YMODULES)
	pyang --ietf $(YMODULES)
